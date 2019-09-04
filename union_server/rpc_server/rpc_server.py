#!/usr/bin/env python
import pika
import yaml
import os
import json
from api_helper import get_request, post_request

import logging
logger = logging.getLogger(__name__)


class RPCServer():
    def __init__(self):
        username = os.getenv('RABBITMQ_DEFAULT_USER')
        password = os.getenv('RABBITMQ_DEFAULT_PASS')
        credentials = pika.PlainCredentials(username, password)

        broker_url = os.getenv('BROKER_URL', '')

        connection = pika.BlockingConnection(
            pika.ConnectionParameters(host=broker_url,
                                      credentials=credentials)
        )

        self.channel = connection.channel()
        self.channel.queue_declare(queue='rpc_queue')

        self.bot_name = ''
        self.config = {}
        with open("union_config.yml", 'r') as stream:
            try:
                self.config = yaml.safe_load(stream)
            except yaml.YAMLError as exc:
                logger.error(exc)

    def get_best_answer(self, answers):
        # TODO: Fazer a hierarquia das policies, antes da confiança

        try:
            max_confidence = max([answer['total_confidence'] for answer in answers])
        except ValueError:
            # Empty answers
            max_confidence = 0

        # FIXME: use the value directly from policy_config.yml, smallest of the thresholds
        if(max_confidence >= 0.6):
            best_answer = self.find_answer_by_confidence(answers, max_confidence)
        else:
            best_answer = self.main_bot_fallback()
        return best_answer

    def main_bot_fallback(self):
        return  {
                    'bot': self.bot_name,
                    'total_confidence': 2,
                    'intent_confidence': 1,
                    'utter_confidence': 1,
                    'policy_name': 'Fallback',
                    'intent_name': 'fallback',
                    'messages':[
                        "Desculpe, ainda não sei falar sobre isso ou talvez não consegui entender direito.",
                        "Você pode perguntar de novo de outro jeito?"
                    ]
                }

    def get_ask_list(self, bot_name):
        bots_urls = []
        ask_to = self.config[bot_name]['ask_to']

        if 'all' in ask_to:
            bots_urls = [v.get('url')[0] for v in self.config.values()]
        else:
            pass

        return bots_urls

    def get_answer_info(self, message, bot_url):
        payload = {'query': message}
        payload = json.dumps(payload)
    
        r = get_request(payload, "http://" + bot_url + "/conversations/default/tracker")

        answer_info = {}
    
        iterator = iter(r['events'])
        for event in iterator:
            if 'event' in event and 'user' == event['event']:
                if message == event['text']:
                    answer_info['intent_confidence'] = event['parse_data']['intent']['confidence'] 
                    answer_info['intent_name'] = event['parse_data']['intent']['name']
                    
                    # always after a user event, there is a action event with policy info.
                    answer_info['utter_confidence'], answer_info['policy_name'] = self.get_policy_info(iterator)
    
                    break

        if answer_info == {}:
            answer_info['intent_confidence'] = -1
            answer_info['intent_name'] = "no answer"

        if not answer_info['intent_name']:
            answer_info['intent_name'] = "Fallback"
        
        return answer_info

    def send_message(self, text, bot_url):
        payload = {'query': text}
        payload = json.dumps(payload)

        r = post_request(payload, "http://" + bot_url + "/conversations/default/respond")

        messages = []

        for i in range(0, len(r)):
            messages.append(r[i]['text'])

        return messages

    def ask_bots(self, text, bot_name):
        answers = []
        bots_urls = self.get_ask_list(bot_name)

        for bot in bots_urls:
            try:
                messages = self.send_message(text, bot)
                info = self.get_answer_info(text, bot)

                if "fallback" in info['policy_name'].lower():
                    continue

                bot_answer = {
                    "bot": bot,
                    "messages": messages,
                    "intent_name": info['intent_name'],
                    "intent_confidence": info['intent_confidence'],
                    "utter_confidence": info['utter_confidence'],
                    "total_confidence": info['intent_confidence']+info['utter_confidence'],
                    "policy_name": info['policy_name'],
                }
                answers.append(bot_answer)
            except Exception as exc:
                logger.warn("Bot didn't answer: " + bot)
                logger.warn("Connection Error: ")
                logger.warn(exc)

        answer = self.get_best_answer(answers)

        return answer

    def on_request(self, ch, method, props, body):
        bot_message = json.loads(body.decode('utf-8'))['bot_message']
        self.bot_name = json.loads(body.decode('utf-8'))['bot_name']

        answer = self.ask_bots(bot_message, self.bot_name)

        logger.warning(answer)
    
        ch.basic_publish(exchange='',
                         routing_key=props.reply_to,
                         properties=pika.BasicProperties(correlation_id = \
                                                            props.correlation_id),
                         body=json.dumps(answer))
        ch.basic_ack(delivery_tag=method.delivery_tag)

    def get_policy_info(self, iterator):
        event = next(iterator)
        if event['event'] != 'action':
            raise ValueError("Event after user event is not a action event")

        return (event['confidence'], event['policy'])

    def find_answer_by_confidence(self, answers, confidence):
        best_answer = {}
        for answer in answers:
            if(answer["total_confidence"] == confidence):
                best_answer = answer

        return best_answer

    def start_server(self):
        self.channel.basic_qos(prefetch_count=1)
        self.channel.basic_consume(queue='rpc_queue',
                              on_message_callback=self.on_request)
        
        logger.warning(" [x] Awaiting RPC requests")
        self.channel.start_consuming()


if __name__ == '__main__':
    rpc_server = RPCServer()
    rpc_server.start_server()
