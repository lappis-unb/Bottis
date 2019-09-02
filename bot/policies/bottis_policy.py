import zlib

import base64
import json
import logging
import os
from tqdm import tqdm
from typing import Optional, Any, Dict, List, Text

from rasa_core import utils
from rasa_core.domain import Domain
from rasa_core.events import ActionExecuted, SlotSet
from rasa_core.featurizers import (
    TrackerFeaturizer, MaxHistoryTrackerFeaturizer)
from rasa_core.policies.policy import Policy
from rasa_core.trackers import DialogueStateTracker
from rasa_core.actions.action import ACTION_LISTEN_NAME
from .api_helper import get_request, post_request


logger = logging.getLogger(__name__)


class BottisPolicy(Policy):
    def __init__(self,
                 priority: int = 2,
                 nlu_threshold: float = 0.7,
                 core_threshold: float = 0.7,
                 custom_response_action_name: Text = "action_custom_response",
                 featurizer: Optional[TrackerFeaturizer] = None,
                 max_history: Optional[int] = None,
                 lookup: Optional[Dict] = None
                 ) -> None:

        self.custom_response_action_name = custom_response_action_name
        self.core_threshold = core_threshold
        self.nlu_threshold = nlu_threshold
        self.priority = priority
        super(BottisPolicy, self).__init__(featurizer, priority)

    def train(self,
              training_trackers: List[DialogueStateTracker],
              domain: Domain,
              **kwargs: Any
              ) -> None:
        """Pretending to train the bots policy."""

        logger.warning("Olaaaa, estou treinando genteee")

    def bottis_score(self, result, domain, bottis_score=1.0):
        idx = domain.index_for_action(self.custom_response_action_name)
        result[idx] = self.core_threshold

        return result

    def predict_action_probabilities(self,
                                     tracker: DialogueStateTracker,
                                     domain: Domain) -> List[float]:
        """Predicts the next action the bot should take
        after seeing the tracker.
        Returns the list of probabilities for the next actions"""

        # TODO: Inserção das API's sem ser hardcode
        bots = ['aix:5005', 'tais:5005', 'defensoria:5005', 'lappisudo:5005']

        # TODO: Paralelizar o envio das mensagens para as APIs cadastradas
        """ TODO: Configurar os dados que recebemos do
        tracker em uma struct separada
        """
        result = [0.0] * domain.num_actions
        intent = tracker.latest_message.intent
        if tracker.latest_action_name == self.custom_response_action_name:
            result = [0.0] * domain.num_actions
            idx = domain.index_for_action(ACTION_LISTEN_NAME)
            result[idx] = 1.0
        elif (intent.get('name') is None and
              intent.get('confidence') < self.nlu_threshold):

            text = tracker.latest_message.text or ''

            answers = self.ask_bots(text, bots)
            answer = self.get_best_answer(answers)

            logger.info("\n\n -- Answer Selected -- ")
            logger.info("Bot: " + answer["bot"])
            logger.info("Confidence: " + str(answer["intent_confidence"]))
            logger.info("Confidence: " + str(answer["utter_confidence"]))
            logger.info("Total Confidence: " + str(answer["total_confidence"]))
            logger.info("Policy: " + str(answer["policy_name"]))
            logger.info("Intent Name: " + answer["intent_name"])

            set_answer_slot_event = SlotSet("bot_answers", answer['messages'])
            tracker.update(set_answer_slot_event)

            result = self.bottis_score(result, domain, self.core_threshold)

        return result

    def persist(self, path: Text) -> None:
        """Persists the policy to storage."""

        config_file = os.path.join(path, 'bottis_policy.json')
        meta = {
                "priority": self.priority,
                "nlu_threshold": self.nlu_threshold,
                "core_threshold": self.core_threshold,
                "custom_response_action_name": self.custom_response_action_name
                }
        utils.create_dir_for_file(config_file)
        utils.dump_obj_as_json_to_file(config_file, meta)

    @classmethod
    def load(cls, path: Text) -> 'BottisPolicy':
        meta = {}
        if os.path.exists(path):
            meta_path = os.path.join(path, "bottis_policy.json")
            if os.path.isfile(meta_path):
                meta = json.loads(utils.read_file(meta_path))

        return cls(**meta)

    def get_best_answer(self, answers):
        # TODO: Fazer a hierarquia das policies, antes da confiança
        # fallback_threshold = self.fallback_threshold
        fallback_threshold = 0.5
        valid_answers = filter(
            lambda x: x['intent_confidence'] >= fallback_threshold,
            answers
            )

        try:
            max_confidence = max(
                [answer['total_confidence'] for answer in valid_answers])
        except ValueError:
            # Empty answers
            max_confidence = 0

        if(valid_answers and max_confidence != 0):
            best_answer =
            self.find_answer_by_confidence(
                answers,
                max_confidence
            )
        else:
            best_answer = main_bot_fallback()

        return best_answer

    def find_answer_by_confidence(self, answers, confidence):
        best_answer = {}
        for answer in answers:
            if(answer["total_confidence"] == confidence):
                best_answer = answer

        return best_answer

    def ask_bots(self, text, bots):
        answers = []
        for bot in bots:
            try:
                messages = self.send_message(text, bot)
                info = self.get_answer_info(text, bot)
                if "fallback" in info['policy_name'].lower():
                    continue
                total_c = info['intent_confidence'] + info['utter_confidence']
                bot_answer = {
                    "bot": bot,
                    "messages": messages,
                    "intent_name": info['intent_name'],
                    "intent_confidence": info['intent_confidence'],
                    "utter_confidence": info['utter_confidence'],
                    "total_confidence": total_c,
                    "policy_name": info['policy_name'],
                }
                answers.append(bot_answer)
            except Exception as e:
                logger.warn("Bot didn't answer: " + bot)
                logger.warn("Connection Error")
                logger.warn(e)

        return answers

    def send_message(self, text, bot_url):
        payload = {'query': text}
        payload = json.dumps(payload)
        url = "http://" + bot_url + "/conversations/default/respond"
        r = post_request(payload, url)
        messages = []
        for i in range(0, len(r)):
            messages.append(r[i]['text'])
        return messages

    def get_answer_info(self, message, bot_url):
        payload = {'query': message}
        payload = json.dumps(payload)

        url = "http://" + bot_url + "/conversations/default/tracker"
        r = get_request(payload, url)
        answer_info = {}

        iterator = iter(r['events'])
        for event in iterator:
            if 'event' in event and 'user' == event['event']:
                if message == event['text']:
                    confidence = event['parse_data']['intent']['confidence']
                    name = event['parse_data']['intent']['name']
                    answer_info['intent_confidence'] = confidence
                    answer_info['intent_name'] = name

                    """We assumed the API returns after a user event,
                    there will be an action event with policy info.
                    """
                    answer_info['utter_confidence'],
                    answer_info['policy_name'] = self.get_policy_info(iterator)

                    break

        if answer_info == {}:
            answer_info['intent_confidence'] = -1
            answer_info['intent_name'] = "no answer"

        if not answer_info['intent_name']:
            answer_info['intent_name'] = "Fallback"

        return answer_info

    def get_policy_info(self, iterator):
        event = next(iterator)
        if event['event'] != 'action':
            raise ValueError("Event after user event is not a action event")

        return (event['confidence'], event['policy'])


def main_bot_fallback():
    return {
                'bot': 'main-bot',
                'total_confidence': 2,
                'intent_confidence': 1,
                'utter_confidence': 1,
                'policy_name': 'Fallback',
                'intent_name': 'fallback',
                'messages': [
                    "Desculpe, ainda não sei falar sobre isso ou talvez não \
                    consegui entender direito.",
                    "Você pode perguntar de novo de outro jeito?"
                ]
            }
