import os
import logging
import importlib

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TOKEN = os.environ.get("BOT_TOKEN")

# ─── Загрузка тестов ───────────────────────────────────────────────────────
# Добавь сюда ID модуля когда создашь новый тест в папке tests/

AVAILABLE_TESTS = [
    "narcissism",
    # "attachment",   # раскомментируй когда добавишь файл tests/attachment.py
    # "alexithymia",  # раскомментируй когда добавишь файл tests/alexithymia.py
    # "defense",      # раскомментируй когда добавишь файл tests/defense.py
    # "stress",       # раскомментируй когда добавишь файл tests/stress.py
]

TESTS = {}
for test_id in AVAILABLE_TESTS:
    module = importlib.import_module(f"tests.{test_id}")
    TESTS[module.TEST_ID] = module

ANSWERS = [
    ("1 — совсем не про меня", 1),
    ("2 — скорее не про меня", 2),
    ("3 — частично про меня",  3),
    ("4 — скорее про меня",    4),
    ("5 — абсолютно про меня", 5),
]

# ─── Меню ──────────────────────────────────────────────────────────────────

def build_menu_keyboard() -> InlineKeyboardMarkup:
    keyboard = [
        [InlineKeyboardButton(module.TEST_TITLE, callback_data=f"select_{test_id}")]
        for test_id, module in TESTS.items()
    ]
    return InlineKeyboardMarkup(keyboard)


def build_answer_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(label, callback_data=f"answer_{value}")]
        for label, value in ANSWERS
    ])

# ─── Хэндлеры ──────────────────────────────────────────────────────────────

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    context.user_data.clear()
    await update.message.reply_text(
        "Привет! Выбери тест который хочешь пройти.",
        reply_markup=build_menu_keyboard(),
    )


async def show_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    context.user_data.clear()
    query = update.callback_query
    await query.answer()
    await query.message.reply_text(
        "Выбери тест:",
        reply_markup=build_menu_keyboard(),
    )


async def select_test(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    test_id = query.data.replace("select_", "")
    module = TESTS.get(test_id)

    if not module:
        await query.message.reply_text("Тест не найден.")
        return

    context.user_data["test_id"] = test_id
    context.user_data["answers"] = []
    context.user_data["current"] = 0

    await query.message.reply_text(
        f"{module.TEST_TITLE}\n\n{module.TEST_DESCRIPTION}\n\nНачинаем?",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("Начать", callback_data="start_test")],
            [InlineKeyboardButton("← Назад", callback_data="menu")],
        ]),
    )


async def start_test(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    await send_question(update, context)


async def send_question(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    test_id = context.user_data.get("test_id")
    module = TESTS.get(test_id)
    idx = context.user_data.get("current", 0)
    total = len(module.QUESTIONS)
    question = module.QUESTIONS[idx]

    text = f"Вопрос {idx + 1} из {total}\n\n{question}"

    if update.callback_query:
        await update.callback_query.message.reply_text(
            text, reply_markup=build_answer_keyboard()
        )
    else:
        await update.message.reply_text(
            text, reply_markup=build_answer_keyboard()
        )


async def handle_answer(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    value = int(query.data.replace("answer_", ""))
    context.user_data["answers"].append(value)
    context.user_data["current"] += 1

    await query.edit_message_reply_markup(reply_markup=None)

    test_id = context.user_data.get("test_id")
    module = TESTS.get(test_id)

    if context.user_data["current"] < len(module.QUESTIONS):
        await send_question(update, context)
    else:
        await show_result(update, context)


async def show_result(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    test_id = context.user_data.get("test_id")
    module = TESTS.get(test_id)
    answers = context.user_data["answers"]

    data = module.calculate_result(answers)
    result = data["result"]
    scores = data["scores"]

    scores_text = "\n".join(
        f"{s['name']}: {s['score']}/30 ({s['level']})" if s['level']
        else f"{s['name']}: {s['score']}"
        for s in scores
    )

    message = (
        f"Твой профиль: {result['title']}\n\n"
        f"{scores_text}\n\n"
        f"{'─' * 30}\n\n"
        f"{result['text']}\n\n"
        f"{'─' * 30}\n\n"
        "Это не диагноз. Результат отражает выраженность определённых черт личности."
    )

    await update.callback_query.message.reply_text(
        message,
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("Пройти другой тест", callback_data="menu")],
            [InlineKeyboardButton("Пройти ещё раз", callback_data=f"select_{test_id}")],
        ]),
    )

# ─── Запуск ────────────────────────────────────────────────────────────────

def main() -> None:
    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(show_menu,    pattern="^menu$"))
    app.add_handler(CallbackQueryHandler(select_test,  pattern="^select_"))
    app.add_handler(CallbackQueryHandler(start_test,   pattern="^start_test$"))
    app.add_handler(CallbackQueryHandler(handle_answer, pattern="^answer_"))

    logger.info("Бот запущен")
    app.run_polling()


if __name__ == "__main__":
    main()
