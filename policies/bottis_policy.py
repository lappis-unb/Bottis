import zlib
import base64
import json
import logging
import os
import uuid
import pika
import sys
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

        # Flag to verify if rabbitmq is connected or needs to be initialized
        self.connected = False
    
    def on_response(self, ch, method, props, body):
        if self.corr_id == props.correlation_id:
            self.response = body
            ch.basic_ack(delivery_tag = method.delivery_tag)
    
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
        if not self.connected:
            self.connect_to_rabbit()

        result = [0.0] * domain.num_actions
        intent = tracker.latest_message.intent
        if tracker.latest_action_name == self.custom_response_action_name:
            result = [0.0] * domain.num_actions
            idx = domain.index_for_action(ACTION_LISTEN_NAME)
            result[idx] = 1.0
        elif (intent.get('name') is None and
              intent.get('confidence') < self.nlu_threshold):

            text = tracker.latest_message.text or ''

            answer = self.call(text)

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

    def connect_to_rabbit(self):
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
    
        self.connected = True

    @classmethod
    def load(cls, path: Text) -> 'BottisPolicy':

        meta = {}
        if os.path.exists(path):
            meta_path = os.path.join(path, "bottis_policy.json")
            if os.path.isfile(meta_path):
                meta = json.loads(utils.read_file(meta_path))

        return cls(**meta)
