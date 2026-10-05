from curl_cffi import requests
from bs4 import BeautifulSoup


class SutBonch:
    BASE_URL = "https://www.sut.ru"
    SCHEDULE_PATH = "/studentu/raspisanie/raspisanie-zanyatiy-studentov-ochnoy-i-vecherney-form-obucheniya"

    DAYS = {
        "rasp-day1": "Понедельник",
        "rasp-day2": "Вторник",
        "rasp-day3": "Среда",
        "rasp-day4": "Четверг",
        "rasp-day5": "Пятница",
        "rasp-day6": "Суббота",
    }

    def __init__(self):
        self.session = requests.Session(impersonate="chrome120")

    def start_session(self, page_url: str) -> BeautifulSoup:
        resp = self.session.get(page_url, timeout=30)
        if resp.status_code != 200:
            raise RuntimeError(f"HTTP {resp.status_code} для {page_url}")
        return BeautifulSoup(resp.text, "html.parser")

    def get_group_schedule_link(self, group_name: str) -> str | None:
        page_url = self.BASE_URL + self.SCHEDULE_PATH
        soup = self.start_session(page_url)

        link = soup.find("a", class_="vt256", attrs={"data-nm": group_name})
        if not link or not link.get("href"):
            return None

        href = link["href"]
        if href.startswith("http"):
            return href
        return self.BASE_URL + self.SCHEDULE_PATH + href

    def parse_schedule(self, soup: BeautifulSoup) -> list[dict]:
        lessons = []

        for row in soup.select("div.vt244b > div.vt244"):
            header = row.find("div", class_="vt239")
            if not header:
                continue

            pair_num_tag = header.find("div", class_="vt283")
            if not pair_num_tag:
                continue
            pair_num = pair_num_tag.get_text(strip=True)

            times = [t for t in header.stripped_strings if ":" in t]
            time_start = times[0] if len(times) > 0 else ""
            time_end = times[1] if len(times) > 1 else ""

            for cell in row.find_all("div", class_="rasp-day"):
                day_name = next(
                    (self.DAYS[c] for c in cell.get("class", []) if c in self.DAYS),
                    None,
                )
                if not day_name:
                    continue

                # В одной ячейке может быть несколько занятий
                for item in cell.find_all("div", class_="vt258"):
                    subject = item.find("div", class_="vt240")
                    teacher = item.find("div", class_="vt241")
                    room = item.find("div", class_="vt242")
                    kind = item.find("div", class_="vt243")

                    teacher_full = ""
                    if teacher:
                        span = teacher.find("span", class_="teacher")
                        if span and span.get("title"):
                            teacher_full = span["title"].strip().rstrip(";")
                        else:
                            teacher_full = teacher.get_text(strip=True)

                    lessons.append({
                        "pair": pair_num,
                        "time_start": time_start,
                        "time_end": time_end,
                        "day": day_name,
                        "subject": subject.get_text(strip=True) if subject else "",
                        "teacher": teacher_full,
                        "room": room.get_text(strip=True) if room else "",
                        "kind": kind.get_text(strip=True) if kind else "",
                    })

        return lessons

    def get_schedule(self, group_name: str) -> list[dict]:
        url = self.get_group_schedule_link(group_name)
        if not url:
            raise ValueError(f"Группа {group_name!r} не найдена")

        soup = self.start_session(url)
        return self.parse_schedule(soup)

if __name__ == "__main__":
    bonch = SutBonch()
    lessons = bonch.get_schedule("ИКТ-2643")

    for lesson in lessons:
        print(
            f"{lesson['day']:11} | {lesson['pair']} пара "
            f"{lesson['time_start']}-{lesson['time_end']} | "
            f"{lesson['subject']} | {lesson['kind']} | "
            f"{lesson['teacher']} | {lesson['room']}"
        )