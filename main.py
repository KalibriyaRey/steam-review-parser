import asyncio
import aiohttp
import threading
import os
import customtkinter as ctk
from tkinter import messagebox

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

POPULAR_GAMES = {
    "Rust": 252490,
    "CS2": 730,
    "Dota 2": 570,
    "GTA V": 271590,
    "Cyberpunk 2077": 1091500,
    "Elden Ring": 1245620,
    "Valheim": 892970,
    "Palworld": 1623730,
}

class SteamReviewParserApp:
    def __init__(self):
        self.root = ctk.CTk()
        self.root.title("Steam Review Parser • Custom Thinker")
        self.root.geometry("600x500")
        self.root.resizable(False, False)

        ctk.CTkLabel(self.root, text="Steam Review Parser", font=("Arial", 20, "bold")).pack(pady=15)

        # Выбор игры
        ctk.CTkLabel(self.root, text="Выберите игру или введите AppID:").pack(anchor="w", padx=20)
        self.game_var = ctk.StringVar(value="Другое (введите AppID)")
        self.game_combo = ctk.CTkComboBox(
            self.root,
            values=list(POPULAR_GAMES.keys()) + ["Другое (введите AppID)"],
            variable=self.game_var,
            width=300,
            command=self.on_game_select
        )
        self.game_combo.pack(pady=5)

        # Поле AppID — сразу видимо
        self.appid_entry = ctk.CTkEntry(self.root, placeholder_text="AppID", width=300)
        self.appid_entry.pack(pady=5)

        # Мин. часы = 0 по умолчанию
        ctk.CTkLabel(self.root, text="Минимальное время игры (часы):").pack(anchor="w", padx=20, pady=(15, 0))
        self.hours_entry = ctk.CTkEntry(self.root, placeholder_text="0", width=300)
        self.hours_entry.insert(0, "0")
        self.hours_entry.pack()

        # Страницы = 20 по умолчанию
        ctk.CTkLabel(self.root, text="Количество страниц (макс. 150):").pack(anchor="w", padx=20, pady=(10, 0))
        self.pages_entry = ctk.CTkEntry(self.root, placeholder_text="20", width=300)
        self.pages_entry.insert(0, "20")
        self.pages_entry.pack()

        # Кнопка
        self.start_btn = ctk.CTkButton(
            self.root,
            text="Запустить парсинг",
            command=self.start_parsing,
            width=200,
            height=40,
            font=("Arial", 14)
        )
        self.start_btn.pack(pady=20)

        # Статус и прогресс
        self.status_label = ctk.CTkLabel(self.root, text="", text_color="gray")
        self.status_label.pack()

        self.progress = ctk.CTkProgressBar(self.root, width=400)
        self.progress.set(0)
        self.progress.pack(pady=5)

        self.review_count_label = ctk.CTkLabel(self.root, text="Отзывов собрано: 0")
        self.review_count_label.pack()

        # Принудительно вызываем обработчик, чтобы поле AppID осталось видимым
        self.on_game_select("Другое (введите AppID)")

    def on_game_select(self, choice):
        if choice == "Другое (введите AppID)":
            self.appid_entry.pack(pady=5)
        else:
            self.appid_entry.pack_forget()

    def get_app_id(self):
        choice = self.game_var.get()
        if choice == "Другое (введите AppID)":
            try:
                return int(self.appid_entry.get().strip())
            except ValueError:
                messagebox.showerror("Ошибка", "Пожалуйста, введите корректный AppID (целое число).")
                raise
        else:
            return POPULAR_GAMES.get(choice, 252490)

    def start_parsing(self):
        try:
            app_id = self.get_app_id()
            min_hours = int(self.hours_entry.get() or 0)
            max_pages = min(int(self.pages_entry.get() or 20), 150)
            if max_pages < 1:
                max_pages = 20
        except Exception as e:
            messagebox.showerror("Ошибка ввода", str(e))
            return

        self.start_btn.configure(state="disabled")
        self.status_label.configure(text="Запуск парсинга...")
        self.progress.set(0)
        self.review_count_label.configure(text="Отзывов собрано: 0")

        thread = threading.Thread(
            target=self.run_async_parser,
            args=(app_id, min_hours, max_pages),
            daemon=True
        )
        thread.start()

    def run_async_parser(self, app_id, min_hours, max_pages):
        try:
            asyncio.run(self.parse_reviews_async(app_id, min_hours, max_pages))
        except Exception as e:
            self.root.after(0, lambda: messagebox.showerror("Ошибка", f"Парсинг завершился с ошибкой:\n{e}"))
            self.root.after(0, self.enable_button)

    async def parse_reviews_async(self, app_id, min_hours, max_pages):
        min_sec = min_hours * 3600
        semaphore = asyncio.Semaphore(12)
        reviews_collected = []
        pages_done = 0
        next_cursor = "*"

        connector = aiohttp.TCPConnector(limit=50, limit_per_host=15)
        timeout = aiohttp.ClientTimeout(total=15)

        async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:

            while pages_done < max_pages and next_cursor:
                self.root.after(0, lambda p=pages_done+1: self.status_label.configure(text=f"Загрузка страницы {p}..."))

                params = {
                    "json": "1",
                    "language": "russian",
                    "num_per_page": "20",
                    "cursor": next_cursor
                }

                for attempt in range(3):
                    try:
                        async with semaphore:
                            async with session.get(
                                f"https://store.steampowered.com/appreviews/{app_id}",
                                params=params
                            ) as resp:
                                if resp.status == 200:
                                    data = await resp.json()
                                    break
                                elif resp.status == 429:
                                    await asyncio.sleep(2)
                                    continue
                                else:
                                    await asyncio.sleep(1)
                                    continue
                    except Exception:
                        await asyncio.sleep(1)
                        continue
                else:
                    break

                if data.get("success") != 1:
                    break

                for rev in data.get("reviews", []):
                    author = rev.get("author", {})
                    playtime = author.get("playtime_forever", 0)
                    text = rev.get("review", "").strip()
                    if playtime >= min_sec and text:
                        reviews_collected.append(text)

                next_cursor = data.get("cursor", "")
                if not next_cursor or next_cursor == "*":
                    next_cursor = None

                pages_done += 1
                progress = pages_done / max_pages
                self.root.after(0, lambda r=len(reviews_collected): self.review_count_label.configure(text=f"Отзывов собрано: {r}"))
                self.root.after(0, lambda p=progress: self.progress.set(p))

                await asyncio.sleep(0.01)

        filename = f"steam_reviews_{app_id}_{min_hours}h.txt"
        with open(filename, "w", encoding="utf-8") as f:
            f.write("\n".join(reviews_collected))

        full_path = os.path.abspath(filename)
        self.root.after(0, lambda: self.status_label.configure(text=f"✅ Готово! Файл: {filename}"))
        self.root.after(0, lambda: messagebox.showinfo("Успех", f"Собрано {len(reviews_collected)} отзывов.\nФайл сохранён:\n{full_path}"))
        self.root.after(0, self.enable_button)

    def enable_button(self):
        self.start_btn.configure(state="normal")

    def run(self):
        self.root.mainloop()

if __name__ == "__main__":
    app = SteamReviewParserApp()
    app.run()
