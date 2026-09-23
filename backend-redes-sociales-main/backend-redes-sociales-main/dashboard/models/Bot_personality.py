from django.db import models
from django.utils import timezone


class BotPersonality(models.Model):
    """
    - Name: El nombre de la personalidad del bot.
    - Bio: Una breve descripción o biografía de la personalidad del bot.
    - Location: La ubicación geográfica donde reside la personalidad del bot.
    - CommunicationStyle: El estilo de comunicación preferido del bot ('Formal', 'Informal', 'Friendly', 'Serious', 'Humorous', 'Sarcastic'),
    - Values: Los valores centrales que la personalidad del bot debe reflejar.
    - Preferences: Las preferencias de la personalidad del bot.
    - Dislikes: Las aversiones de la personalidad del bot.
    - ExampleResponses: Ejemplos de cómo debería responder el bot a ciertas situaciones o preguntas.
    - SpecialKnowledge: Cualquier conocimiento o habilidad especial que la personalidad del bot posea.
    - CulturalReferences: Referencias culturales específicas que la personalidad del bot debe entender o utilizar.
    - Phraseology: Frases o modismos típicos que la personalidad del bot podría usar.
    - PastInteractions: Datos sobre interacciones pasadas que el bot ha tenido y cómo respondió en esos casos.
    - EmotionalReactions: Cómo debería reaccionar el bot emocionalmente ante diferentes tipos de estímulos o situaciones.
    - Objectives: Los objetivos que la personalidad del bot está tratando de alcanzar en sus interacciones.
    - BehavioralTendencies: Cualquier tendencia comportamental notable que quieras que la personalidad del bot exhiba.
    """

    name = models.CharField(max_length=255, null=True, blank=True)
    bio = models.TextField(null=True, blank=True)
    location = models.CharField(max_length=255, null=True, blank=True)
    language = models.CharField(max_length=255, default="ESPAÑOL")
    communication_style = models.TextField(null=True, blank=True)
    values = models.TextField(null=True, blank=True)
    preferences = models.TextField(null=True, blank=True)
    dislikes = models.TextField(null=True, blank=True)
    example_responses = models.TextField(null=True, blank=True)
    special_knowledge = models.TextField(null=True, blank=True)
    cultural_references = models.TextField(null=True, blank=True)
    phraseology = models.TextField(null=True, blank=True)
    past_interactions = models.TextField(null=True, blank=True)
    emotional_reactions = models.TextField(null=True, blank=True)
    objectives = models.TextField(null=True, blank=True)
    behavioral_tendencies = models.TextField(null=True, blank=True)

    def __str__(self):
        return self.name
