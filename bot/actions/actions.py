from rasa_core_sdk import Action


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
        text = tracker.get_slot('bot_answer')

        dispatcher.utter_message(text)

        return [SlotSet('bot_answer', '')]
