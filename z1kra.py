#made by OneDop
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Updater, CommandHandler, CallbackContext, ApplicationBuilder
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.jobstores.base import ConflictingIdError
from prayer_times_calculator import PrayerTimesCalculator
from datetime import datetime, timedelta
import os

Cities = {
    "Riyadh": [24.7136, 46.6753, "makkah"],
    "Mecca": [21.3891, 39.8579, "makkah"],
    "Jeddah": [21.4858, 39.1925, "makkah"],
    "Dubai": [25.276987, 55.296249, "dubai"],
    "Abu Dhabi": [24.453884, 54.377344, "dubai"],
    "Cairo": [30.0444, 31.2357, "egypt"],
    "Alexandria": [31.2156, 29.9553, "egypt"],
    "Baghdad": [33.3152, 44.3661, "mwl"],
    "Basra": [30.5085, 47.8106, "mwl"],
    "Damascus": [33.5138, 36.2765, "mwl"],
    "Aleppo": [36.2021, 37.1343, "mwl"],
    "Amman": [31.9539, 35.9106, "jordan"],
    "Zarqa": [32.0729, 36.0880, "jordan"],
    "Irbid": [32.5569, 35.8470, "jordan"],
    "Aqaba": [29.5320, 35.0061, "jordan"],
    "Mafraq": [32.3434, 36.2080, "jordan"],
    "Beirut": [33.8938, 35.5018, "mwl"],
    "Kuwait City": [29.3759, 47.9774, "kuwait"],
    "Doha": [25.276987, 51.52245, "qatar"],
    "Muscat": [23.5880, 58.3829, "gulf"],
    "Manama": [26.2285, 50.5860, "gulf"],
    "Rabat": [34.0209, -6.8416, "morocco"],
    "Casablanca": [33.5731, -7.5898, "morocco"],
    "Algiers": [36.7372, 3.0869, "algeria"],
    "Tunis": [36.8065, 10.1815, "tunisia"],
    "Tripoli": [32.8872, 13.1913, "mwl"],
    "Khartoum": [15.5007, 32.5599, "mwl"],
    "Sana'a": [15.3694, 44.1910, "mwl"]
}

def get_times(city):
    info = Cities[city]
    times = PrayerTimesCalculator(info[0], info[1], info[2], str(datetime.now().date())).fetch_prayer_times()
    relevant_prayers = ["Fajr", "Dhuhr", "Asr", "Maghrib","Isha"]
    filtered_times = {prayer: times[prayer] for prayer in relevant_prayers if prayer in times}
    return filtered_times

async def send_prayer_reminder(context: CallbackContext):
    job = context.job
    prayer_name = job.context['prayer_name']
    chat_id = job.context['chat_id']
    await context.bot.send_message(chat_id=chat_id, text=f"Time for {prayer_name} prayer!")


async def start(update: Update, context: CallbackContext) -> None:
   await update.message.reply_text(
        "Welcome to the Prayer Times Bot! Use /prayertimes <city> to get prayer times for your city.")

async def about(update: Update, context: CallbackContext) -> None:
    await update.message.reply_text("This bot provides Islamic prayer times and reminders based on your city.")
    await update.message.reply_text("بوت للتذكير بالصلاة و ساعة الاستجابة للدعاء يوم الجمعة حسب مدينتك")


async def subscribe(update: Update, context: CallbackContext) -> None:
    if len(context.args) < 1:
        await update.message.reply_text("Please provide a city. Example: /subscribe mecca")
        return

    city = context.args[0]
    if city not in Cities:
        await update.message.reply_text(f"City '{city}' not recognized. Please choose a valid city.")
        return

    chat_id = update.message.chat_id
    times = get_times(city)

    for prayer, time in times.items():
        prayer_time = datetime.strptime(time, '%H:%M').time()
        try:
            context.job_queue.run_daily(
                send_prayer_reminder,
                time=prayer_time,
                chat_id= chat_id,
                data={'prayer_name': prayer, 'chat_id': chat_id},
                name=f"{chat_id}_{city}_{prayer}"
            )
        except ConflictingIdError:
            pass  # Ignore duplicate jobs

    await update.message.reply_text(f"You have subscribed to daily prayer reminders for {city}.")


async def unsubscribe(update: Update, context: CallbackContext):
    chat_id = update.message.chat_id
    removed_jobs = 0

    for job in context.job_queue.jobs():
        if str(chat_id) in job.name:
            job.schedule_removal()
            removed_jobs += 1

    if removed_jobs > 0:
        await update.message.reply_text("You have unsubscribed from all daily prayer time reminders.")
    else:
        await update.message.reply_text("No active reminders found to unsubscribe.")


async def set_jumuah_reminder(update: Update, context: CallbackContext):
    if len(context.args) < 1:
        await update.message.reply_text("Please provide a city. Example: /setjumuahreminder Amman")
        return

    city = context.args[0]
    if city not in Cities:
        await update.message.reply_text(f"City '{city}' not recognized. Please choose a valid city.")
        return

    chat_id = update.message.chat_id
    times = get_times(city)
    maghrib_time = datetime.strptime(times['Maghrib'], '%H:%M')
    fajr_time = datetime.strptime(times['Fajr'], '%H:%M')
    duaa_hour = maghrib_time - (maghrib_time - fajr_time) / 12

    context.job_queue.run_daily(
        lambda context: context.bot.send_message(chat_id=chat_id, text="Duaa Hour!"),
        time=duaa_hour.time(),
        days=(4,),  # Friday
        chat_id=chat_id,
        name=f"{chat_id}_jumuah"
    )
    await update.message.reply_text(f"Jumu'ah and Duaa Hour reminders set for {city}!")


async def stop_jumuah_reminder(update: Update, context: CallbackContext):
    chat_id = update.message.chat_id
    job_name = f"{chat_id}_jumuah"
    for job in context.job_queue.jobs():
        if job.name == job_name:
            job.schedule_removal()
            await update.message.reply_text("Jumu'ah reminder has been stopped.")
            return

    await update.message.reply_text("No active Jumu'ah reminder found.")

async def prayer_times(update: Update, context: CallbackContext):
    if len(context.args) < 1:
        await update.message.reply_text("Please provide a city. Example: /prayertimes mecca")
        return
    city = context.args[0]
    if city not in Cities:
        await update.message.reply_text(f"City '{city}' not recognized. Please choose a valid city.")
        return
    times = get_times(city)
    msg = "\n".join([f"{prayer}: {time}" for prayer, time in times.items()])
    await update.message.reply_text(msg)

async def available_cities(update: Update, context: CallbackContext):
    msg = "\n".join([f"- {city}" for city in Cities])
    await update.message.reply_text(msg)

def main():
    application = ApplicationBuilder().token("YOUR_TOKEN").build()

    application.add_handler(CommandHandler('start', start))
    application.add_handler(CommandHandler('about', about))
    application.add_handler(CommandHandler('subscribe', subscribe))
    application.add_handler(CommandHandler('unsubscribe', unsubscribe))
    application.add_handler(CommandHandler('prayertimes', prayer_times))
    application.add_handler(CommandHandler('setjumuahreminder', set_jumuah_reminder))
    application.add_handler(CommandHandler('stopjumuahreminder', stop_jumuah_reminder))
    application.add_handler(CommandHandler('available_cities', available_cities))

    application.run_polling()


if __name__ == '__main__':
    main()
