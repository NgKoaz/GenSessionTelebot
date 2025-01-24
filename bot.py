from telegram import * 
from telegram.ext import *
from telethon import *
from util import Util
import asyncio
import threading
import time


class Bot:
    PHONE, _2FA, LOGIN_CODE, = range(3)
    TEMP_DIR = "temp"
    NEGLECT_2FA_QUERY = "neglect_2fa"
    LOGIN_CODE_SHARED_MEM = {}
    EVENT_SHARED_MEM = {}
    SHARED_MEM = {}

    def __init__(self, token: str, api_id: str, api_hash: str):
        self._token = token
        self._api_id = api_id
        self._api_hash = api_hash

        # Init loop
        self.loop = asyncio.get_event_loop() 

        self._app = Application.builder().token(self._token).build()
        self._app.add_handler(ConversationHandler(
            entry_points=[CommandHandler("start", self.start)],
            states={
                Bot.PHONE: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_phone_state)],
                Bot._2FA: [CallbackQueryHandler(callback=self.handle_2fa_query_state), MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_2fa_state)],
                Bot.LOGIN_CODE: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_login_code_state)],
                
            },
            fallbacks=[
                CommandHandler("start", self.start),
                CommandHandler("cancel", self.cancel)
            ],
        ))

        Util.ensure_dir(Bot.TEMP_DIR)
        self._app.run_polling()

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if update.effective_user.id in Bot.EVENT_SHARED_MEM:
            if "allow_to_end" in Bot.EVENT_SHARED_MEM[update.effective_user.id]:
                allow_to_end_event: threading.Event = Bot.EVENT_SHARED_MEM[update.effective_user.id]["allow_to_end"]
                if not allow_to_end_event.isSet():
                    await context.bot.send_message(
                        chat_id = update.effective_chat.id,
                        text="Hãy chờ đợi để tôi kết thúc phiên làm việc trước!"
                    )
                allow_to_end_event.wait()
        await context.bot.send_message(
            chat_id = update.effective_chat.id,
            text="Gửi số điện thoại đăng nhập:"
        )
        return Bot.PHONE

    async def handle_phone_state(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        # Try to correct phone format 
        phone = Util.try_to_correct_phone(update.message.text)

        # Wrong phone format
        if not Util.is_phone(phone):
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="Số điện thoại chỉ chứa + hoặc số từ 0 đến 9! Hãy nhập lại số điện thoại: ",
                parse_mode="HTML"
            )
            return Bot.PHONE
        
        # True phone format
        context.user_data["phone"] = phone
        keyboard = [[
            InlineKeyboardButton("Không có 2FA", callback_data=Bot.NEGLECT_2FA_QUERY)
        ]]
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="Nhập 2FA:",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return Bot._2FA
    
    async def handle_2fa_query_state(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        # Process valid Query
        query = update.callback_query
        if query and query.data == Bot.NEGLECT_2FA_QUERY:
            await query.answer()
            await query.edit_message_reply_markup()

            # Create a new thread with new loop inside for signing process
            print("Creating new thread for sign in telegram...")
            Bot.EVENT_SHARED_MEM[update.effective_user.id] = {
                "allow_to_end": threading.Event(),
                "entered_login_code_event": threading.Event(),
                "sign_in_done_event": threading.Event()
            }
            thread = threading.Thread(target=self.sign_in_telegram, args=(update, context))
            thread.daemon = True
            thread.start()

            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="Gửi Login Code:"
            )
            
            return Bot.LOGIN_CODE
        
        # Process invalid Query
        else:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="Lỗi phát sinh, hãy bắt đầu lại!",
                parse_mode="HTML"
            )
            return ConversationHandler.END

    async def handle_2fa_state(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        context.user_data["2fa"] = update.message.text
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="Nhập Login Code:",
            parse_mode="HTML"
        )
        
        # Create a new thread with new loop inside for signing process
        print("Creating new thread for sign in telegram...")
        Bot.EVENT_SHARED_MEM[update.effective_user.id] = {
            "allow_to_end": threading.Event(),
            "entered_login_code_event": threading.Event(),
            "sign_in_done_event": threading.Event()
        }
        thread = threading.Thread(target=self.sign_in_telegram, args=(update, context))
        thread.daemon = True
        thread.start()

        return Bot.LOGIN_CODE
    
    async def handle_login_code_state(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        # Process bad login code
        login_code = update.message.text
        if not Util.is_login_code(login_code):
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="Nhập lại Login Code:",
                parse_mode="HTML"
            )
            return Bot.LOGIN_CODE
        
        # Process qualified login code
        entered_login_code_event: threading.Event = Bot.EVENT_SHARED_MEM[update.effective_user.id]["entered_login_code_event"]
        sign_in_done_event: threading.Event = Bot.EVENT_SHARED_MEM[update.effective_user.id]["sign_in_done_event"]

        context.user_data["login_code"] = update.message.text
        Bot.LOGIN_CODE_SHARED_MEM[update.effective_user.id] = update.message.text
        print(f"Saved login code `{Bot.LOGIN_CODE_SHARED_MEM[update.effective_user.id]}`")

        entered_login_code_event.set()
        sign_in_done_event.wait()
        session_path = Bot.TEMP_DIR + "/" + context.user_data["phone"] + ".session"
        try:
            if Bot.SHARED_MEM[update.effective_user.id]["isLogged"]:
                await context.bot.send_document(chat_id=update.effective_chat.id, document=session_path)
            else:
                await context.bot.send_message(
                    chat_id=update.effective_chat.id,
                    text="Tạo session thất bại. Hãy bắt đầu lại quy trình!",
                    parse_mode="HTML"
                ) 
        except Exception as e:
            print(e)
            print("[ERROR] KeyError: isLogged = False by default!")
        finally:
            print("Conversation end here!")
            return ConversationHandler.END

    def sign_in_telegram(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        # Create new event loop for new thread
        newLoop = asyncio.new_event_loop()
        asyncio.set_event_loop(newLoop)

        # Create Telegram Client
        phone = context.user_data.get("phone", "")
        _2fa = context.user_data.get("2fa", "")
        session_path = Bot.TEMP_DIR + "/" + phone
        client = TelegramClient(session_path, self._api_id, self._api_hash)

        entered_login_code_event: threading.Event = Bot.EVENT_SHARED_MEM[update.effective_user.id]["entered_login_code_event"]
        sign_in_done_event: threading.Event = Bot.EVENT_SHARED_MEM[update.effective_user.id]["sign_in_done_event"]
        allow_to_end: threading.Event = Bot.EVENT_SHARED_MEM[update.effective_user.id]["allow_to_end"]
        allow_to_end.set()

        # Start connecting to Telegram
        print("Start connecting...")
        def get_otp() -> str:
            entered_login_code_event.wait(timeout=60)
            return Bot.LOGIN_CODE_SHARED_MEM.get(update.effective_user.id)
        Bot.SHARED_MEM[update.effective_user.id] = {}
        try:
            client.start(phone=phone, password=_2fa, code_callback=get_otp, max_attempts=1)
            Bot.SHARED_MEM[update.effective_user.id]["isLogged"] = True
        except Exception as e:
            print(e)
            Bot.SHARED_MEM[update.effective_user.id]["isLogged"] = False
        finally:
            sign_in_done_event.set()
            # Start disconnecting to Telegram
            print("Start disconnecting...")
            client.disconnect()
        print("Close thread!")

    async def cancel(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="Hủy quy trình, mời bạn khởi động lại bằng cách gõ /start",
            parse_mode="HTML"
        )
        return ConversationHandler.END


