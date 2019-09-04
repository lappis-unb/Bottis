import zlib
import base64
import json
import logging
import os
import uuid
import pika
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

        username = os.getenv('RABBITMQ_DEFAULT_USER')
        password = os.getenv('RABBITMQ_DEFAULT_PASS')
        broker_url = os.getenv('BROKER_URL')

        self.bot_name = os.getenv('BOT_NAME')

        credentials = pika.PlainCredentials(username, password)

        self.connection = pika.BlockingConnection(
            pika.ConnectionParameters(host=broker_url,
                                      credentials=credentials)
        )

        self.channel = self.connection.channel()

        result = self.channel.queue_declare(queue='', exclusive=True)
        self.callback_queue = result.method.queue

        self.channel.basic_consume(
            queue=self.callback_queue,
            on_message_callback=self.on_response)

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
    
    def call(self, text):
        self.response = None
        bot_message = {
                       'bot_message': text,
                       'bot_name': self.bot_name
                      }
        self.corr_id = str(uuid.uuid4())
        self.channel.basic_publish(
            exchange='',
            routing_key='rpc_queue',
            properties=pika.BasicProperties(
                reply_to=self.callback_queue,
                correlation_id=self.corr_id,
            ),
            body=json.dumps(bot_message))
        while self.response is None:
            self.connection.process_data_events()
        return json.loads(self.response)
    
    def predict_action_probabilities(self,
                                     tracker: DialogueStateTracker,
                                     domain: Domain) -> List[float]:
        """Predicts the next action the bot should take
        after seeing the tracker.
        Returns the list of probabilities for the next actions"""
        result = [0.0] * domain.num_actions
        intent = tracker.latest_message.intent
        if tracker.latest_action_name == self.custom_response_action_name:
            result = [0.0] * domain.num_actions
            idx = domain.index_for_action(ACTION_LISTEN_NAME)
            result[idx] = 1.0
        elif (intent.get('name') is None and
              intent.get('confidence') < self.nlu_threshold):

            text = tracker.latest_message.text or ''

            # TODO: Inserção das API's sem ser hardcode
            # bots = ["localhost:5006", 'localhost:5007']

            # TODO: Paralelizar o envio das mensagens para as APIs cadastradas
            # TODO: Configurar os dados que recebemos do tracker em uma struct separada
            answer = self.call(text)

            # TODO: Continuar com o Fallback padrão quando nenhum bot tem confiança suficiente
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
