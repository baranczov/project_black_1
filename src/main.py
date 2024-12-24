import asyncio
import logging
import sys

from aiogram import Bot, Dispatcher, F, Router
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramAPIError
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from aiogram.client.default import DefaultBotProperties

from config import BOT_TOKEN, DEBUG, LOGGING_LEVEL
from api_requests import get_weather_info

logging.basicConfig(
    level=LOGGING_LEVEL,
    stream=sys.stdout,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    encoding="utf-8",
)
logger = logging.getLogger(__name__)

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()
router = Router()
dp.include_router(router)


class WeatherStates(StatesGroup):
    waiting_for_start_point = State()
    waiting_for_end_point = State()
    waiting_for_intermediate = State()
    waiting_for_interval = State()


def get_route_keyboard() -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(text="➕ Добавить точку маршрута", callback_data="add_point")],
        [InlineKeyboardButton(text="✅ Завершить маршрут", callback_data="finish_route")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_interval_keyboard() -> InlineKeyboardMarkup:
    buttons = [
        [
            InlineKeyboardButton(text="1 день", callback_data="interval_1"),
            InlineKeyboardButton(text="2 дня", callback_data="interval_2"),
            InlineKeyboardButton(text="3 дня", callback_data="interval_3"),
        ],
        [
            InlineKeyboardButton(text="4 дня", callback_data="interval_4"),
            InlineKeyboardButton(text="5 дней", callback_data="interval_5"),
        ],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


@router.message(CommandStart())
async def command_start(message: Message) -> None:
    await message.answer(
        "👋 Привет! Я бот прогноза погоды.\n"
        "Я помогу узнать погоду на вашем маршруте.\n"
        "Используйте /help для получения списка команд."
    )


@router.message(Command("help"))
async def command_help_handler(message: Message) -> None:
    help_text = (
        "🌤 <b>Доступные команды:</b>\n\n"
        "/start - Начать работу с ботом\n"
        "/help - Показать это сообщение\n"
        "/weather - Получить прогноз погоды\n\n"
        "Для получения прогноза погоды используйте команду /weather "
        "и следуйте инструкциям."
    )
    await message.answer(help_text)


@router.message(Command("weather"))
async def command_weather(message: Message, state: FSMContext) -> None:
    await state.set_state(WeatherStates.waiting_for_start_point)
    await message.answer("🌍 Укажите начальную точку маршрута\n(Например: Москва)")


@router.message(WeatherStates.waiting_for_start_point)
async def process_start_point(message: Message, state: FSMContext) -> None:
    await state.update_data(start_point=message.text)
    await state.set_state(WeatherStates.waiting_for_end_point)
    await message.answer("📍 Отлично! Теперь укажите конечную точку маршрута")


@router.message(WeatherStates.waiting_for_end_point)
async def process_end_point(message: Message, state: FSMContext) -> None:
    await state.update_data(end_point=message.text, intermediate_points=[])
    keyboard = get_route_keyboard()
    await message.answer("🛣 Маршрут почти готов! Хотите добавить промежуточные точки?", reply_markup=keyboard)


@router.callback_query(F.data == "add_point")
async def process_add_point(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(WeatherStates.waiting_for_intermediate)
    await callback.message.answer("📍 Укажите промежуточную точку маршрута")
    await callback.answer()


@router.message(WeatherStates.waiting_for_intermediate)
async def process_intermediate_point(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    points = data.get("intermediate_points", [])
    points.append(message.text)
    await state.update_data(intermediate_points=points)

    keyboard = get_route_keyboard()
    await message.answer(
        f"✅ Точка {message.text} добавлена! Хотите добавить еще?",
        reply_markup=keyboard,
    )


@router.callback_query(F.data == "finish_route")
async def process_finish_route(callback: CallbackQuery, state: FSMContext) -> None:
    keyboard = get_interval_keyboard()
    await state.set_state(WeatherStates.waiting_for_interval)
    await callback.message.answer("⏱ Выберите интервал прогноза:", reply_markup=keyboard)
    await callback.answer()


@router.callback_query(F.data.startswith("interval_"))
async def process_interval(callback: CallbackQuery, state: FSMContext) -> None:
    interval = int(callback.data.split("_")[1])
    data = await state.get_data()

    route_info = f"🚩 <b>Ваш маршрут:</b>\nНачало: {data['start_point']}\n"

    if data.get("intermediate_points"):
        route_info += "\nПромежуточные точки:\n"
        for i, point in enumerate(data["intermediate_points"], 1):
            route_info += f"{i}. {point}\n"

    route_info += (
        f"\nКонец: {data['end_point']}\n"
        f"\n📅 Прогноз будет составлен на {interval} дня(дней)"
    )

    await callback.message.answer(route_info)

    weather_info = get_weather_info(data, interval, get_cached=DEBUG)
    await callback.message.answer(
        "🌍 Маршрут построен!\n\n"
        "🌤 Прогноз погоды на маршруте:\n" + weather_info
    )

    await state.clear()
    await callback.answer()


@router.message()
async def echo_handler(message: Message) -> None:
    await message.answer(
        "Извините, я не понимаю эту команду.\n"
        "Используйте /help для получения списка доступных команд."
    )


@router.errors()
async def handle_error(event: TelegramAPIError):
    try:
        logger.error("Произошла ошибка: %s", str(event.exception))
        if event.update.message:
            await event.update.message.answer(
                "Извините, произошла ошибка при обработке запроса."
            )
    except Exception as e:
        logger.error("Ошибка при обработке ошибки: %s", str(e))


async def main() -> None:
    logger.info("Starting bot...")
    try:
        await dp.start_polling(
            bot, allowed_updates=dp.resolve_used_update_types()
        )
    except TelegramAPIError as e:
        logger.error(f"Telegram API Error: {e}")
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
    finally:
        await bot.session.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped!")
