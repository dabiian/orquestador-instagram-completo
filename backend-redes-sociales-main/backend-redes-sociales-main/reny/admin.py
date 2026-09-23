from django.contrib import admin

# Register your models here.
from .models import JSONData, Acount, QuestionAndAnswer


admin.site.register(JSONData)
admin.site.register(Acount)
admin.site.register(QuestionAndAnswer)
