from django.db import models


class JSONData(models.Model):
    data = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.created_at.strftime("%Y-%m-%d %H:%M:%S")


class Acount(models.Model):
    credenciales = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.created_at.strftime("%Y-%m-%d %H:%M:%S")


class QuestionAndAnswer(models.Model):
    data = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.created_at.strftime("%Y-%m-%d %H:%M:%S")
