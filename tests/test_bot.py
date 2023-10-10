async def test_top_level_command(bot, plugin):
    await bot.send("!admin")
    assert len(bot.sent) == 1
    expected = (
        "**Usage:** !admin <subcommand> [...]\n\n"
        "● !admin <subcommand> [...] - Admin Commands\n"
        "● list - List Rooms this bot is in\n"
        "● leave <room_id> - Leave a Room\n"
        "● join <room_id_or_alias> - Join a Room\n"
        "● send-message <room_id> <text> - Send a message to a room"
    )
    assert bot.sent[0].content.body == expected
