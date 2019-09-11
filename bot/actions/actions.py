from rasa_core_sdk import Action
from rasa_core.events import SlotSet


class ActionTest(Action):
    def name(self):
        return "action_test"

    def run(self, dispatcher, tracker, domain):
        try:
            dispatcher.utter_message("Mensagem enviada por uma custom action.")
        except ValueError:
            dispatcher.utter_message(ValueError)

class ActionCustomResponse(Action):
    def name(self):
        return "action_custom_response"

    def run(self, dispatcher, tracker, domain):
        messages = tracker.get_slot('bot_answers')

        for message in messages:
            dispatcher.utter_message(message)