from django.contrib import admin

from .models.Bot_personality import BotPersonality
from .models.bot_execution import (
    BotExecutionArtifact,
    BotExecutionReport,
    BotExecutionStep,
)
from .models.social_media_platform import SocialMediaPlatform
from .models.account_owner import AccountOwner
from .models.social_media_account import SocialMediaAccount
from .models.task_type import TaskType
from .models.task_bot import TaskBot
from .models.proxy import Proxy
from .models.Bot_personality import BotPersonality

admin.site.register(BotPersonality)
admin.site.register(SocialMediaPlatform)
admin.site.register(AccountOwner)
admin.site.register(SocialMediaAccount)
admin.site.register(TaskType)
admin.site.register(TaskBot)
admin.site.register(Proxy)
admin.site.register(BotExecutionReport)
admin.site.register(BotExecutionStep)
admin.site.register(BotExecutionArtifact)
