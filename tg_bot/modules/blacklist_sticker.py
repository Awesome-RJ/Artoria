import html
from typing import Optional

from telegram import Chat, ChatPermissions, Message, ParseMode, User
from telegram.error import BadRequest
from telegram.ext import CommandHandler, Filters, MessageHandler
from telegram.ext.dispatcher import run_async
from telegram.utils.helpers import mention_html, mention_markdown

import tg_bot.modules.sql.blsticker_sql as sql
from tg_bot import LOGGER, REDIS, dispatcher
from tg_bot.modules.connection import connected
from tg_bot.modules.disable import DisableAbleCommandHandler
from tg_bot.modules.helper_funcs.alternate import send_message
from tg_bot.modules.helper_funcs.chat_status import user_admin, user_not_admin
from tg_bot.modules.helper_funcs.misc import split_message
from tg_bot.modules.helper_funcs.string_handling import extract_time
from tg_bot.modules.log_channel import loggable
from tg_bot.modules.warns import warn


@run_async
def blackliststicker(update, context):
    msg = update.effective_message  # type: Optional[Message]
    chat = update.effective_chat  # type: Optional[Chat]
    user = update.effective_user  # type: Optional[User]
    bot, args = context.bot, context.args
    if conn := connected(bot, update, chat, user.id, need_admin=False):
        chat_id = conn
        chat_name = dispatcher.bot.getChat(conn).title
    else:
        if chat.type == "private":
            return
        chat_id = update.effective_chat.id
        chat_name = chat.title

    sticker_list = "<b>List blacklisted stickers currently in {}:</b>\n".format(
        chat_name
    )

    all_stickerlist = sql.get_chat_stickers(chat_id)

    if len(args) > 0 and args[0].lower() == "copy":
        for trigger in all_stickerlist:
            sticker_list += "<code>{}</code>\n".format(html.escape(trigger))
    elif len(args) == 0:
        for trigger in all_stickerlist:
            sticker_list += " - <code>{}</code>\n".format(html.escape(trigger))

    split_text = split_message(sticker_list)
    for text in split_text:
        if sticker_list == "<b>List blacklisted stickers currently in {}:</b>\n".format(
            chat_name
        ).format(chat_name):
            send_message(
                update.effective_message,
                "There are no blacklist stickers in <b>{}</b>!".format(chat_name),
                parse_mode=ParseMode.HTML,
            )
            return
    send_message(msg, text, parse_mode=ParseMode.HTML)


@run_async
@user_admin
def add_blackliststicker(update, context):
    bot = context.bot
    msg = update.effective_message  # type: Optional[Message]
    chat = update.effective_chat  # type: Optional[Chat]
    user = update.effective_user  # type: Optional[User]
    words = msg.text.split(None, 1)
    if conn := connected(bot, update, chat, user.id):
        chat_id = conn
        chat_name = dispatcher.bot.getChat(conn).title
    else:
        chat_id = update.effective_chat.id
        if chat.type == "private":
            return
        chat_name = chat.title

    if len(words) > 1:
        text = words[1].replace("https://t.me/addstickers/", "")
        to_blacklist = list(
            {trigger.strip() for trigger in text.split("\n") if trigger.strip()}
        )
        added = 0
        for trigger in to_blacklist:
            try:
                bot.getStickerSet(trigger)
                sql.add_to_stickers(chat_id, trigger.lower())
                added += 1
            except BadRequest:
                send_message(
                    update.effective_message,
                    "Sticker `{}` can not be found!".format(trigger),
                    parse_mode="markdown",
                )

        if added == 0:
            return

        if len(to_blacklist) == 1:
            send_message(
                update.effective_message,
                "Sticker <code>{}</code> added to blacklist stickers in <b>{}</b>!".format(
                    html.escape(to_blacklist[0]), chat_name
                ),
                parse_mode=ParseMode.HTML,
            )
        else:
            send_message(
                update.effective_message,
                "<code>{}</code> stickers added to blacklist sticker in <b>{}</b>!".format(
                    added, chat_name
                ),
                parse_mode=ParseMode.HTML,
            )
    elif msg.reply_to_message:
        added = 0
        trigger = msg.reply_to_message.sticker.set_name
        if trigger is None:
            send_message(update.effective_message, "Sticker is invalid!")
            return
        try:
            bot.getStickerSet(trigger)
            sql.add_to_stickers(chat_id, trigger.lower())
            added += 1
        except BadRequest:
            send_message(
                update.effective_message,
                "Sticker `{}` can not be found!".format(trigger),
                parse_mode="markdown",
            )

        if added == 0:
            return

        send_message(
            update.effective_message,
            "Sticker <code>{}</code> added to blacklist stickers in <b>{}</b>!".format(
                trigger, chat_name
            ),
            parse_mode=ParseMode.HTML,
        )
    else:
        send_message(
            update.effective_message,
            "Tell me what stickers you want to add to the blacklist.",
        )


@run_async
@user_admin
def unblackliststicker(update, context):
    bot = context.bot
    msg = update.effective_message  # type: Optional[Message]
    chat = update.effective_chat  # type: Optional[Chat]
    user = update.effective_user  # type: Optional[User]
    words = msg.text.split(None, 1)
    if conn := connected(bot, update, chat, user.id):
        chat_id = conn
        chat_name = dispatcher.bot.getChat(conn).title
    else:
        chat_id = update.effective_chat.id
        if chat.type == "private":
            return
        chat_name = chat.title

    if len(words) > 1:
        text = words[1].replace("https://t.me/addstickers/", "")
        to_unblacklist = list(
            {trigger.strip() for trigger in text.split("\n") if trigger.strip()}
        )
        successful = 0
        for trigger in to_unblacklist:
            success = sql.rm_from_stickers(chat_id, trigger.lower())
            if success:
                successful += 1

        if len(to_unblacklist) == 1:
            if successful:
                send_message(
                    update.effective_message,
                    "Sticker <code>{}</code> deleted from blacklist in <b>{}</b>!".format(
                        html.escape(to_unblacklist[0]), chat_name
                    ),
                    parse_mode=ParseMode.HTML,
                )
            else:
                send_message(
                    update.effective_message, "This sticker is not on the blacklist...!"
                )

        elif successful == len(to_unblacklist):
            send_message(
                update.effective_message,
                "Sticker <code>{}</code> deleted from blacklist in <b>{}</b>!".format(
                    successful, chat_name
                ),
                parse_mode=ParseMode.HTML,
            )

        elif not successful:
            send_message(
                update.effective_message,
                "None of these stickers exist, so they cannot be removed.",
                parse_mode=ParseMode.HTML,
            )

        else:
            send_message(
                update.effective_message,
                "Sticker <code>{}</code> deleted from blacklist. {} did not exist, so it's not deleted.".format(
                    successful, len(to_unblacklist) - successful
                ),
                parse_mode=ParseMode.HTML,
            )
    elif msg.reply_to_message:
        trigger = msg.reply_to_message.sticker.set_name
        if trigger is None:
            send_message(update.effective_message, "Sticker is invalid!")
            return
        success = sql.rm_from_stickers(chat_id, trigger.lower())

        if success:
            send_message(
                update.effective_message,
                "Sticker <code>{}</code> deleted from blacklist in <b>{}</b>!".format(
                    trigger, chat_name
                ),
                parse_mode=ParseMode.HTML,
            )
        else:
            send_message(
                update.effective_message,
                "{} not found on blacklisted stickers...!".format(trigger),
            )
    else:
        send_message(
            update.effective_message,
            "Tell me what stickers you want to add to the blacklist.",
        )


@run_async
@loggable
@user_admin
def blacklist_mode(update, context):
    chat = update.effective_chat  # type: Optional[Chat]
    user = update.effective_user  # type: Optional[User]
    msg = update.effective_message  # type: Optional[Message]
    bot, args = context.bot, context.args
    conn = connected(bot, update, chat, user.id, need_admin=True)
    if conn:
        chat = dispatcher.bot.getChat(conn)
        chat_id = conn
        chat_name = dispatcher.bot.getChat(conn).title
    else:
        if msg.chat.type == "private":
            send_message(msg, "You can do this command in groups, not PM")
            return ""
        chat = update.effective_chat
        chat_id = update.effective_chat.id
        chat_name = msg.chat.title

    if args:
        if args[0].lower() in ["off", "nothing", "no"]:
            settypeblacklist = "turn off"
            sql.set_blacklist_strength(chat_id, 0, "0")
        elif args[0].lower() in ["del", "delete"]:
            settypeblacklist = "left, the message will be deleted"
            sql.set_blacklist_strength(chat_id, 1, "0")
        elif args[0].lower() == "warn":
            settypeblacklist = "warned"
            sql.set_blacklist_strength(chat_id, 2, "0")
        elif args[0].lower() == "mute":
            settypeblacklist = "muted"
            sql.set_blacklist_strength(chat_id, 3, "0")
        elif args[0].lower() == "kick":
            settypeblacklist = "kicked"
            sql.set_blacklist_strength(chat_id, 4, "0")
        elif args[0].lower() == "ban":
            settypeblacklist = "banned"
            sql.set_blacklist_strength(chat_id, 5, "0")
        elif args[0].lower() == "tban":
            if len(args) == 1:
                teks = """It looks like you are trying to set a temporary value to blacklist, but has not determined \
                the time; use `/blstickermode tban <timevalue>`. Examples of time values: \
                4m = 4 minute, 3h = 3 hours, 6d = 6 days, 5w = 5 weeks.
                """
                send_message(msg, teks, parse_mode="markdown")
                return
            settypeblacklist = "temporary banned for {}".format(args[1])
            sql.set_blacklist_strength(chat_id, 6, str(args[1]))
        elif args[0].lower() == "tmute":
            if len(args) == 1:
                teks = """It looks like you are trying to set a temporary value to blacklist, but has not determined\
                 the time; use `/blstickermode tmute <timevalue>`. Examples of time values: \
                 4m = 4 minute, 3h = 3 hours, 6d = 6 days, 5w = 5 weeks.
                 """
                send_message(msg, teks, parse_mode="markdown")
                return
            settypeblacklist = "temporary muted for {}".format(args[1])
            sql.set_blacklist_strength(chat_id, 7, str(args[1]))
        else:
            send_message(
                msg,
                "I only understand off/del/warn/ban/kick/mute/tban/tmute!",
            )
            return
        if conn:
            text = "Blacklist sticker mode changed, users will be `{}` at *{}*!".format(
                settypeblacklist, chat_name
            )
        else:
            text = "Blacklist sticker mode changed, users will be `{}`!".format(
                settypeblacklist
            )
        send_message(update.effective_message, text, parse_mode="markdown")
        return (
            "<b>{}:</b>\n"
            "<b>Admin:</b> {}\n"
            "Changed sticker blacklist mode. users will be {}.".format(
                html.escape(chat.title),
                mention_html(user.id, user.first_name),
                settypeblacklist,
            )
        )

    getmode, getvalue = sql.get_blacklist_setting(chat.id)
    if getmode == 0:
        settypeblacklist = "not active"
    elif getmode == 1:
        settypeblacklist = "hapus"
    elif getmode == 2:
        settypeblacklist = "warn"
    elif getmode == 3:
        settypeblacklist = "mute"
    elif getmode == 4:
        settypeblacklist = "kick"
    elif getmode == 5:
        settypeblacklist = "ban"
    elif getmode == 6:
        settypeblacklist = "temporarily banned for {}".format(getvalue)
    elif getmode == 7:
        settypeblacklist = "temporarily muted for {}".format(getvalue)
    if conn:
        text = "Blacklist sticker mode is currently set to *{}* in *{}*.".format(
            settypeblacklist, chat_name
        )
    else:
        text = "Blacklist sticker mode is currently set to *{}*.".format(
            settypeblacklist
        )
    send_message(update.effective_message, text, parse_mode=ParseMode.MARKDOWN)
    return ""


@run_async
@user_not_admin
def del_blackliststicker(update, context):
    chat = update.effective_chat  # type: Optional[Chat]
    message = update.effective_message  # type: Optional[Message]
    user = update.effective_user
    to_match = message.sticker
    if not to_match:
        return

    chat_id = str(chat.id)[1:]
    approve_list = list(REDIS.sunion(f"approve_list_{chat_id}"))
    target_user = mention_html(user.id, user.first_name)
    if target_user in approve_list:
        return

    bot = context.bot
    getmode, value = sql.get_blacklist_setting(chat.id)

    chat_filters = sql.get_chat_stickers(chat.id)
    for trigger in chat_filters:
        if to_match.set_name.lower() == trigger.lower():
            try:
                if getmode == 0:
                    return
                if getmode == 1:
                    message.delete()
                elif getmode == 2:
                    message.delete()
                    warn(
                        update.effective_user,
                        chat,
                        "Using sticker '{}' which in blacklist stickers".format(
                            trigger
                        ),
                        message,
                        update.effective_user,
                        # conn=False,
                    )
                    return
                elif getmode == 3:
                    message.delete()
                    bot.restrict_chat_member(
                        chat.id,
                        update.effective_user.id,
                        permissions=ChatPermissions(can_send_messages=False),
                    )
                    bot.sendMessage(
                        chat.id,
                        "{} muted because using '{}' which in blacklist stickers".format(
                            mention_markdown(user.id, user.first_name), trigger
                        ),
                        parse_mode="markdown",
                    )
                    return
                elif getmode == 4:
                    message.delete()
                    res = chat.unban_member(update.effective_user.id)
                    if res:
                        bot.sendMessage(
                            chat.id,
                            "{} kicked because using '{}' which in blacklist stickers".format(
                                mention_markdown(user.id, user.first_name), trigger
                            ),
                            parse_mode="markdown",
                        )
                    return
                elif getmode == 5:
                    message.delete()
                    chat.kick_member(user.id)
                    bot.sendMessage(
                        chat.id,
                        "{} banned because using '{}' which in blacklist stickers".format(
                            mention_markdown(user.id, user.first_name), trigger
                        ),
                        parse_mode="markdown",
                    )
                    return
                elif getmode == 6:
                    message.delete()
                    bantime = extract_time(message, value)
                    chat.kick_member(user.id, until_date=bantime)
                    bot.sendMessage(
                        chat.id,
                        "{} banned for {} because using '{}' which in blacklist stickers".format(
                            mention_markdown(user.id, user.first_name), value, trigger
                        ),
                        parse_mode="markdown",
                    )
                    return
                elif getmode == 7:
                    message.delete()
                    mutetime = extract_time(message, value)
                    bot.restrict_chat_member(
                        chat.id,
                        user.id,
                        permissions=ChatPermissions(
                            can_send_messages=False, until_date=mutetime
                        ),
                    )
                    bot.sendMessage(
                        chat.id,
                        "{} muted for {} because using '{}' which in blacklist stickers".format(
                            mention_markdown(user.id, user.first_name), value, trigger
                        ),
                        parse_mode="markdown",
                    )
                    return
            except BadRequest as excp:
                if excp.message != "Message to delete not found":
                    LOGGER.exception("Error while deleting blacklist message.")
                break


def __import_data__(chat_id, data):
    # set chat blacklist
    blacklist = data.get("sticker_blacklist", {})
    for trigger in blacklist:
        sql.add_to_blacklist(chat_id, trigger)


def __migrate__(old_chat_id, new_chat_id):
    sql.migrate_chat(old_chat_id, new_chat_id)


def __chat_settings__(chat_id, _):
    blacklisted = sql.num_stickers_chat_filters(chat_id)
    return "There are `{} `blacklisted stickers.".format(blacklisted)


__mod_name__ = "BL Stickers"

BLACKLIST_STICKER_HANDLER = DisableAbleCommandHandler(
    "blsticker", blackliststicker, admin_ok=True
)
ADDBLACKLIST_STICKER_HANDLER = DisableAbleCommandHandler(
    "addblsticker", add_blackliststicker
)
UNBLACKLIST_STICKER_HANDLER = CommandHandler(
    ["unblsticker", "rmblsticker"], unblackliststicker
)
BLACKLISTMODE_HANDLER = CommandHandler("blstickermode", blacklist_mode)
BLACKLIST_STICKER_DEL_HANDLER = MessageHandler(
    Filters.sticker & Filters.group, del_blackliststicker
)

dispatcher.add_handler(BLACKLIST_STICKER_HANDLER)
dispatcher.add_handler(ADDBLACKLIST_STICKER_HANDLER)
dispatcher.add_handler(UNBLACKLIST_STICKER_HANDLER)
dispatcher.add_handler(BLACKLISTMODE_HANDLER)
dispatcher.add_handler(BLACKLIST_STICKER_DEL_HANDLER)
