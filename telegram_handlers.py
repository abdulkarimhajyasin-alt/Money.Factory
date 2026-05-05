from telegram.ext import CallbackQueryHandler, CommandHandler, MessageHandler, filters


_handlers_registered = False


def _has_registered_callback(app, callback):
    for handler_group in app.handlers.values():
        for registered_handler in handler_group:
            if getattr(registered_handler, "callback", None) is callback:
                return True
    return False


def register_telegram_handlers(app, handlers):
    global _handlers_registered

    if _handlers_registered:
        return
    _handlers_registered = True

    command_handlers = [
        ("start", handlers.start),
        ("k", handlers.k),
        ("ana", handlers.ana),
        ("admin", handlers.admin_panel),
        ("send", handlers.send_to_all),
        ("approve", handlers.approve),
        ("userinfo", handlers.userinfo),
        ("resetpass", handlers.resetpass),
        ("ban", handlers.ban_user),
        ("unban", handlers.unban_user),
        ("freeze", handlers.freeze_user),
        ("unfreeze", handlers.unfreeze_user),
        ("blocksupport", handlers.block_support_user),
        ("unblocksupport", handlers.unblock_support_user),
        ("addbalance", handlers.add_balance),
        ("subbalance", handlers.subtract_balance),
        ("setplan", handlers.set_plan),
        ("resetwithdraw", handlers.reset_withdraw_cycle),
    ]

    for command_name, callback in command_handlers:
        app.add_handler(CommandHandler(command_name, callback))

    app.add_handler(CallbackQueryHandler(handlers.handle_admin_buttons))
    app.add_handler(MessageHandler(filters.PHOTO, handlers.handle_photo))
    app.add_handler(MessageHandler(filters.Document.ALL, handlers.handle_document))
    if not _has_registered_callback(app, handlers.handle_message):
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handlers.handle_message))
