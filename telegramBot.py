import asyncio
from datetime import datetime, time as dtime

from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    Message, CallbackQuery,
    ReplyKeyboardMarkup, KeyboardButton,
    InlineKeyboardMarkup, InlineKeyboardButton,
)

from sut import SutBonch

TOKEN = "8476865534:AAGjSdSUI46CVHx-BhSQi8LlHxyPfkKVbgQ"

bot = Bot(token=TOKEN)
dp = Dispatcher()
sut = SutBonch()

PAIR_TIMES = {
    "1": (dtime(9, 0),  dtime(10, 35)),
    "2": (dtime(10, 45), dtime(12, 20)),
    "3": (dtime(13, 0),  dtime(14, 35)),
    "4": (dtime(14, 45), dtime(16, 20)),
    "5": (dtime(16, 30), dtime(18, 5)),
    "6": (dtime(18, 15), dtime(19, 50)),
}

WEEKDAYS_RU = ["Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота", "Воскресенье"]

class Form(StatesGroup):
    waiting_group = State()
    waiting_action = State()

def actions_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Текущая пара")],
            [KeyboardButton(text="Следующая пара")],
            [KeyboardButton(text="Расписание на сегодня")],
            [KeyboardButton(text="Расписание на завтра")],
            [KeyboardButton(text="Сменить группу")],
        ],
        resize_keyboard=True,
    )

def find_current_lesson(lessons: list[dict]) -> dict | None:
    now = datetime.now()
    today = WEEKDAYS_RU[now.weekday()]
    now_t = now.time()

    for lesson in lessons:
        if lesson["day"] != today:
            continue
        pair = lesson["pair"]
        if pair not in PAIR_TIMES:
            continue
        start, end = PAIR_TIMES[pair]
        if start <= now_t <= end:
            return lesson
    return None


def find_next_lesson(lessons: list[dict]) -> dict | None:
    now = datetime.now()
    today = WEEKDAYS_RU[now.weekday()]
    now_t = now.time()

    today_lessons = [l for l in lessons if l["day"] == today and l["pair"] in PAIR_TIMES]
    today_lessons.sort(key=lambda l: PAIR_TIMES[l["pair"]][0])

    for lesson in today_lessons:
        start, _ = PAIR_TIMES[lesson["pair"]]
        if start > now_t:
            return lesson

    today_idx = now.weekday()
    for offset in range(1, 7):
        idx = (today_idx + offset) % 7
        day_name = WEEKDAYS_RU[idx]
        day_lessons = [l for l in lessons if l["day"] == day_name and l["pair"] in PAIR_TIMES]
        if day_lessons:
            day_lessons.sort(key=lambda l: PAIR_TIMES[l["pair"]][0])
            return day_lessons[0]
    return None


def format_lesson(lesson: dict, header: str) -> str:
    pair = lesson["pair"]
    start, end = PAIR_TIMES.get(pair, ("", ""))
    time_range = f"{lesson['time_start']}-{lesson['time_end']}" or f"{start}-{end}"
    return (
        f"<b>{header}</b>\n\n"
        f"<b>{lesson['subject']}</b>\n"
        f"{lesson['pair']} пара ({time_range})\n"
        f"{lesson['room']}\n"
        f"{lesson['teacher']}\n"
        f"{lesson['kind']}"
    )


def format_day(lessons: list[dict], day_name: str) -> str:
    day_lessons = [l for l in lessons if l["day"] == day_name]
    if not day_lessons:
        return f"<b>{day_name}</b>\n\nЗанятий нет 🎉"

    day_lessons.sort(key=lambda l: PAIR_TIMES.get(l["pair"], (dtime(23, 59),))[0])
    lines = [f"<b>{day_name}</b>\n"]
    for l in day_lessons:
        lines.append(
            f"\n<b>{l['pair']} пара</b> {l['time_start']}-{l['time_end']}\n"
            f"{l['subject']}\n"
            f"{l['room']} | 👤 {l['teacher']}\n"
            f"{l['kind']}"
        )
    return "\n".join(lines)

@dp.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "Привет! Я бот расписания СПбГУТ 🎓\n\n"
        "Напиши номер группы (например, <code>ИКТ-2643</code>):",
        parse_mode="HTML",
    )
    await state.set_state(Form.waiting_group)


@dp.message(Form.waiting_group)
async def got_group(message: Message, state: FSMContext):
    group = message.text.strip().upper()

    await message.answer("⏳ Загружаю расписание...")

    try:
        lessons = await asyncio.to_thread(sut.get_schedule, group)
    except ValueError:
        await message.answer(
            f"❌ Группа <code>{group}</code> не найдена.\n"
            "Попробуй ещё раз:",
            parse_mode="HTML",
        )
        return
    except Exception as e:
        await message.answer(f"⚠️ Ошибка загрузки: <code>{e}</code>", parse_mode="HTML")
        return

    await state.update_data(group=group, lessons=lessons)
    await state.set_state(Form.waiting_action)
    await message.answer(
        f"✅ Группа <b>{group}</b> загружена.\n\nЧто показать?",
        reply_markup=actions_kb(),
        parse_mode="HTML",
    )


@dp.message(Form.waiting_action)
async def handle_action(message: Message, state: FSMContext):
    data = await state.get_data()
    group = data.get("group")
    lessons = data.get("lessons") or []
    text = message.text

    if text == "Сменить группу":
        await state.clear()
        await message.answer(
            "Напиши номер новой группы:",
            reply_markup=None,
        )
        await state.set_state(Form.waiting_group)
        return

    if text == "Текущая пара":
        lesson = find_current_lesson(lessons)
        if lesson:
            await message.answer(
                format_lesson(lesson, "Сейчас идёт:"),
                parse_mode="HTML",
            )
        else:
            await message.answer("Сейчас пары нет 🎉")
        return

    if text == "Следующая пара":
        lesson = find_next_lesson(lessons)
        if lesson:
            await message.answer(
                format_lesson(lesson, "Следующая пара:"),
                parse_mode="HTML",
            )
        else:
            await message.answer("На ближайшие дни пар нет")
        return

    if text == "Расписание на сегодня":
        today = WEEKDAYS_RU[datetime.now().weekday()]
        await message.answer(format_day(lessons, today), parse_mode="HTML")
        return

    if text == "Расписание на завтра":
        tomorrow_idx = (datetime.now().weekday() + 1) % 7
        tomorrow = WEEKDAYS_RU[tomorrow_idx]
        await message.answer(format_day(lessons, tomorrow), parse_mode="HTML")
        return

    await message.answer("Не понял команду. Выбери кнопку ниже", reply_markup=actions_kb())

async def main():
    print("Бот запущен")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())