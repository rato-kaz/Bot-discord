import os
from discord.ext import commands


def is_owner():
    """Check xem user có phải owner của bot không (dựa trên OWNER_ID trong .env)."""
    def predicate(ctx):
        owner_id = os.getenv("OWNER_ID")
        if not owner_id:
            return False
        return ctx.author.id == int(owner_id)
    return commands.check(predicate)
