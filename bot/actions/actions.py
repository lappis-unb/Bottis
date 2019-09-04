

env = environ.Env()

class ActionTest(Action):
    def name(self):
        return "action_test"

    def run(self, dispatcher, tracker, domain):
        try:
            dispatcher.utter_message("Mensagem enviada por uma custom action.")
        except ValueError:
            dispatcher.utter_message(ValueError)

import json
import pika
import uuid
import environ
import logging
import os
logger = logging.getLogger(__name__)

env = environ.Env()

class ActionTest(Action):
    def name(self):
        return "action_test"

    def run(self, dispatcher, tracker, domain):
        try:
            dispatcher.utter_message("Mensagem enviada por uma custom action.")
        except ValueError:
            dispatcher.utter_message(ValueError)

def get_bots_from_env():
    bot_env_var = env.str("BOTS", "")
    bots = []
    # Remove possible extra ; at the end of the string
    if bot_env_var[-1] == ";":
        bot_env_var = bot_env_var[:-1]

    # Create array of bot name to be used in requests
    for bot in bot_env_var.split(';'):
        bots.append(bot)

    logger.warn("-"*100)
    logger.warn("Signed bots to be requests on fallbacks:\n")
    for bot in bots:
        logger.warn(bot)
    logger.warn("-"*100)

    return bots


class ActionFallback(Action):
    def name(self):
        return "action_fallback"

    def on_response(self, ch, method, props, body):
        if self.corr_id == props.correlation_id:
            self.response = body
            ch.basic_ack(delivery_tag = method.delivery_tag)

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

    def __init__(self):
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

    def run(self, dispatcher, tracker, domain):
        text = ''
        text = tracker.latest_message.get('text')

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

        for message in answer["messages"]:
            logger.info("Message: " + message)
            dispatcher.utter_message(message)

        dispatcher.utter_attachment(str(answer))
