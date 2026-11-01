"""Roohi-style extras for clone bots:
help router + clone settings, /nothumb, /loop, button rename commands,
"thanks for adding me" / supergroup check, and voice-chat-started notice.
"""
from pyrogram import Client, filters
from pyrogram.enums import ChatMemberStatus, ChatType
from pyrogram.types import Message

import config
from config import BANNED_USERS, OWNER_ID
from roohifont import fancy, quote
from RoohiClone.misc import SUDOERS
from RoohiClone.utils.database import clonebotdb, get_lang, get_loop, set_loop
from RoohiClone.utils.database.clonedb import get_cloned_support_chat, get_owner_id_from_db
from RoohiClone.utils.roohi import (clone_owner, help_router, is_thumb_on, roohi_edit,
                                  set_thumb, tg_link, thumb_markup, thumb_text)
from strings import get_string


async def _me(client):
    return client.me or await client.get_me()


async def _is_admin(client, chat_id, user_id):
    if user_id in SUDOERS or user_id == OWNER_ID:
        return True
    try:
        if user_id == await get_owner_id_from_db((await _me(client)).id):
            return True
    except Exception:
        pass
    try:
        m = await client.get_chat_member(chat_id, user_id)
        return m.status in (ChatMemberStatus.OWNER, ChatMemberStatus.ADMINISTRATOR)
    except Exception:
        return False


# ------------------------------------------------------------------ help
@Client.on_callback_query(filters.regex(r"^roohihelp ") & ~BANNED_USERS)
async def clone_roohi_help(client, cq):
    key = cq.data.split(None, 1)[1]
    me = await _me(client)
    owner = await get_owner_id_from_db(me.id)
    support = tg_link(await get_cloned_support_chat(me.id))
    await help_router(client, cq, key, is_clone=True,
                      is_owner=cq.from_user.id in (owner, OWNER_ID),
                      support_link=support)


# ------------------------------------------------------------------ /nothumb
@Client.on_message(filters.command(["nothumb", "thumb", "thumbnail"]) & filters.group & ~BANNED_USERS)
async def clone_nothumb(client, message: Message):
    if not message.from_user or not await _is_admin(client, message.chat.id, message.from_user.id):
        return await message.reply_text(quote(f"<b>{fancy('Only admins can change this.')}</b>"))
    on = await is_thumb_on(message.chat.id)
    await message.reply_text(thumb_text(on), reply_markup=thumb_markup(message.chat.id))


@Client.on_callback_query(filters.regex(r"^roohithumb ") & ~BANNED_USERS)
async def clone_nothumb_cb(client, cq):
    action, chat_id = cq.data.split(None, 1)[1].split("|")
    chat_id = int(chat_id)
    if not await _is_admin(client, chat_id, cq.from_user.id):
        return await cq.answer(fancy("Only admins can change this."), show_alert=True)
    await set_thumb(chat_id, action == "on")
    await cq.answer(fancy("Thumbnail enabled") if action == "on" else fancy("Thumbnail disabled"))
    await roohi_edit(cq, thumb_text(action == "on"), thumb_markup(chat_id))


# ------------------------------------------------------------------ /loop (was missing on clones)
@Client.on_message(filters.command(["loop", "cloop"]) & filters.group & ~BANNED_USERS)
async def clone_loop(client, message: Message):
    if not message.from_user or not await _is_admin(client, message.chat.id, message.from_user.id):
        return await message.reply_text(quote(f"<b>{fancy('Only admins can use this.')}</b>"))
    _ = get_string(await get_lang(message.chat.id))
    chat_id = message.chat.id
    if len(message.command) != 2:
        return await message.reply_text(_["admin_17"])
    state = message.command[1].strip().lower()
    if state.isnumeric():
        state = int(state)
        if not 1 <= state <= 10:
            return await message.reply_text(_["admin_17"])
        state = min(10, (await get_loop(chat_id)) + state)
        await set_loop(chat_id, state)
        return await message.reply_text(_["admin_18"].format(state, message.from_user.mention))
    if state == "enable":
        await set_loop(chat_id, 10)
        return await message.reply_text(_["admin_18"].format(10, message.from_user.mention))
    if state == "disable":
        await set_loop(chat_id, 0)
        return await message.reply_text(_["admin_19"].format(message.from_user.mention))
    return await message.reply_text(_["admin_17"])


# ------------------------------------------------------------------ rename start buttons (documented, was missing)
_BTN_KEYS = {
    "setbtnadd": "add", "setbtnsupport": "support", "setbtnchannel": "channel",
    "setbtnowner": "owner", "setbtnhelp": "help",
}


@Client.on_message(filters.command(list(_BTN_KEYS)) & ~BANNED_USERS & clone_owner)
async def rename_btn(client, message: Message):
    key = _BTN_KEYS[message.command[0].lower()]
    if len(message.command) < 2:
        return await message.reply_text(quote(
            f"<b>{fancy('Usage')} :</b> <code>/{message.command[0]} New Text</code>\n"
            f"{fancy('Send')} <code>/{message.command[0]} hide</code> {fancy('to hide this button.')}"))
    text = message.text.split(None, 1)[1].strip()[:40]
    if text.lower() == "hide":
        text = "HIDDEN"
    bot_id = (await _me(client)).id
    await clonebotdb.update_one({"bot_id": bot_id}, {"$set": {f"btn_{key}": text}}, upsert=True)
    await message.reply_text(quote(f"<b>✅ {fancy('Button updated')} :</b> {text}"))


@Client.on_message(filters.command(["resetbtns", "resetbuttons"]) & ~BANNED_USERS & clone_owner)
async def reset_btns(client, message: Message):
    bot_id = (await _me(client)).id
    await clonebotdb.update_one({"bot_id": bot_id},
                                {"$unset": {f"btn_{k}": "" for k in _BTN_KEYS.values()}})
    await message.reply_text(quote(f"<b>✅ {fancy('All button names reset.')}</b>"))


# ------------------------------------------------------------------ added to a group
@Client.on_message(filters.new_chat_members, group=-1)
async def clone_added(client, message: Message):
    me = await _me(client)
    if not any(m.id == me.id for m in message.new_chat_members):
        return
    _ = get_string(await get_lang(message.chat.id))
    if message.chat.type != ChatType.SUPERGROUP:
        support = tg_link(await get_cloned_support_chat(me.id))
        try:
            await message.reply_text(
                f"<b>{me.mention}</b>\n" + quote(
                    f"<b>{fancy('This chat')} (ID: <code>{message.chat.id}</code>) "
                    f"{fancy('is not a supergroup yet.')}</b>")
                + "\n" + quote(
                    f"<b>⚠️ {fancy('Please convert this group into a supergroup, then add me again as an admin.')}</b>\n\n"
                    f"<b>{fancy('How to convert?')}</b> {fancy('Make chat history visible for new members once.')}\n"
                    f"{fancy('If you still face any issues, join our')} <a href=\"{support}\">{fancy('support group')}</a>."),
                disable_web_page_preview=True,
            )
        except Exception:
            pass
        try:
            await client.leave_chat(message.chat.id)
        except Exception:
            pass
        return
    try:
        await message.reply_text(_["start_3"])
    except Exception:
        pass


# ------------------------------------------------------------------ voice chat started
@Client.on_message(filters.video_chat_started, group=21)
async def clone_vc_started(client, message: Message):
    try:
        await message.reply_text(quote(
            f"<b>♻️ {fancy('Voice chat started!')}</b>\n\n"
            f"{fancy('Use')} /play [{fancy('song name')}] {fancy('to play music.')}"))
    except Exception:
        pass


# ------------------------------------------------------------------ clone added to / removed from a group
@Client.on_chat_member_updated(filters.group, group=1)
async def clone_group_event_logger(client: Client, update):
    """Clone bot added to / removed from a group -> clone logger.

    Goes to (1) the global clone log chat (LOGGER_2_ID, sent by the main bot because
    clones are not members there) and (2) the clone owner's own logger
    (/setchannel, falls back to the owner's PM).
    """
    try:
        me = await _me(client)
        new = update.new_chat_member
        if not new or new.user.id != me.id:
            return

        from pyrogram import enums
        from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup
        from RoohiClone import app
        from RoohiClone.cplugin.setinfo import get_log_channel, get_logging_status
        from RoohiClone.utils.logger import get_owner

        added = new.status in (ChatMemberStatus.MEMBER, ChatMemberStatus.ADMINISTRATOR)
        removed = new.status in (ChatMemberStatus.BANNED, ChatMemberStatus.LEFT)
        if not (added or removed):
            return
        # ignore plain member -> admin promotions (old status was already in the chat)
        old = update.old_chat_member
        if added and old and old.status in (ChatMemberStatus.MEMBER, ChatMemberStatus.ADMINISTRATOR):
            return

        chat = update.chat
        by = update.from_user.mention if update.from_user else "<b>Unknown User</b>"
        try:
            members = await client.get_chat_members_count(chat.id)
        except Exception:
            members = "Unknown"
        owner = await get_owner(client, chat.id)

        link = f"https://t.me/{chat.username}" if chat.username else None
        if not link and new.status == ChatMemberStatus.ADMINISTRATOR:
            try:
                link = await client.export_chat_invite_link(chat.id)
            except Exception:
                link = None
        markup = InlineKeyboardMarkup([[InlineKeyboardButton("🔗 ɢʀᴏᴜᴘ ʟɪɴᴋ", url=link)]]) if link else None

        title = "✅ ᴄʟᴏɴᴇ ʙᴏᴛ ᴀᴅᴅᴇᴅ ᴛᴏ ɢʀᴏᴜᴘ" if added else "❌ ᴄʟᴏɴᴇ ʙᴏᴛ ʀᴇᴍᴏᴠᴇᴅ ꜰʀᴏᴍ ɢʀᴏᴜᴘ"
        who = "ᴀᴅᴅᴇᴅ ʙʏ" if added else "ʀᴇᴍᴏᴠᴇᴅ ʙʏ"
        text = (
            f"#{'Added' if added else 'Removed'}\n"
            f"<blockquote><b>{title}</b>\n\n"
            f"<b>• ʙᴏᴛ : @{me.username} (Clone)</b>\n"
            f"<b>• {who} : {by}</b>\n"
            f"<b>• ᴄʜᴀᴛ : {chat.title} [<code>{chat.id}</code>]</b>\n"
            f"<b>• ᴏᴡɴᴇʀ : {owner}</b>\n"
            f"<b>• ᴍᴇᴍʙᴇʀs : {members}</b></blockquote>"
        )
        photo = "https://files.catbox.moe/10zwqs.jpg"

        # (1) global clone log group
        if getattr(config, "LOGGER_2_ID", 0):
            try:
                await app.send_photo(config.LOGGER_2_ID, photo=photo, caption=text, reply_markup=markup)
            except Exception:
                try:
                    await app.send_message(config.LOGGER_2_ID, text, reply_markup=markup,
                                           disable_web_page_preview=True)
                except Exception as e:
                    print(f"[CLONE LOG] global logger failed: {e}")

        # (2) the clone owner's own logger
        try:
            if await get_logging_status(me.id) is False:
                return
        except Exception:
            pass
        target = None
        try:
            target = await get_log_channel(me.id)
        except Exception:
            target = None
        if not target or str(target) in ("-100", "0", "None"):
            try:
                target = await get_owner_id_from_db(me.id)
            except Exception:
                target = None
        if target:
            try:
                await client.send_photo(int(target), photo=photo, caption=text, reply_markup=markup)
            except Exception:
                try:
                    await client.send_message(int(target), text, reply_markup=markup,
                                              disable_web_page_preview=True)
                except Exception as e:
                    print(f"[CLONE LOG] owner logger failed: {e}")
    except Exception as e:
        print(f"[CLONE LOG] clone_group_event_logger failed: {e}")
