run-rocketchat:
	make config-bot
	make download-model
	python3 run-rocketchat.py

run-telegram:
	make download-model
	python -m rasa_core.run -d /models/dialogue -u /models/nlu/current --port 5001 --credentials credentials.yml --endpoints endpoints.yml

config-rocket:
	python /scripts/bot_config.py

run-console:
	make download-model
	python3 -m rasa_core.run -d /models/dialogue -u /models/nlu/current --debug --enable_api --endpoints /bot/endpoints.yml

run-console-broker:
	make download-model
	python3 -m rasa_core.run -d /models/dialogue -u /models/nlu/current --debug --endpoints /bot/endpoints.yml

run-api:
	make download-model
	python3 -m rasa_core.run -d /models/dialogue -u /models/nlu/current \
  --endpoints endpoints.yml --debug --enable_api 

evaluate:
	make download-model
	python3 -m rasa_core.evaluate -d /models/dialogue -s /bot/data/core/

run-actions:
	python -m rasa_core_sdk.endpoint --actions actions

# Force Makefile to execute e2e command every time
.PHONY: all e2e clean
test-dialogue:
	make e2e

e2e:
	python3 -m rasa_core.evaluate default --core /models/dialogue --nlu /models/nlu/current --stories /bot/e2e/e2e_stories.md --e2e

test-stories:
	python3 test_stories.py --stories /bot/e2e/e2e_stories.md --e2e

config-bot:
	python /scripts/bot_config.py -r ${ROCKETCHAT_URL} -an ${ROCKETCHAT_ADMIN_USERNAME} -ap ${ROCKETCHAT_ADMIN_PASSWORD} -bu ${ROCKETCHAT_BOT_USERNAME} -bp ${ROCKETCHAT_BOT_PASSWORD}

download-model:
	python3 /scripts/model_downloader.py