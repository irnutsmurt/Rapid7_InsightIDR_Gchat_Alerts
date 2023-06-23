import requests
import json
import configparser
import os
import json
import httplib2
import logging
from logging.handlers import TimedRotatingFileHandler
from httplib2 import Http
import time
import pytz
from datetime import datetime

# define logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

# set up console handler
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
console_handler.setFormatter(formatter)
logger.addHandler(console_handler)

# set up file handler
file_handler = TimedRotatingFileHandler(filename='alert.log', when='midnight', backupCount=7)
file_handler.setLevel(logging.DEBUG)
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)

# Add debug logs
logger.debug(f"Logging level: {logging.getLevelName(logger.getEffectiveLevel())}")
logger.debug(f"Console handler logging level: {logging.getLevelName(console_handler.level)}")


# read the configuration from config.ini file
config = configparser.ConfigParser()
config.read('config.ini')

# get the InsightIDR API key and region from the config file
insightidr_api_key = config['insightidr']['api_key']
region = config['insightidr']['region']

# get priority_levels from config
priority_levels = config['alerts_field']['priority_levels'].split(',')

# set variable for sent alerts
sent_alert_rrns_file = 'sent_alert_rrns.txt'

# set the InsightIDR API endpoint URL
pacific = pytz.timezone('US/Pacific')
start_time = datetime.now(pacific).strftime('%Y-%m-%dT00:00:00Z')
insightidr_url = f"https://{region}.api.insight.rapid7.com/idr/v2/investigations?filter=created_time>{start_time}"

# set the InsightIDR API headers
insightidr_headers = {
    'X-Api-Key': insightidr_api_key,
    'Content-Type': 'application/json',
    'Accept-version': 'investigations-preview'
}

# set the file path and name for the JSON alert files
raw_alerts_file = 'raw_alerts.json'
formatted_alerts_file = 'formatted_alerts.json'

# define Http object
http_obj = Http()

def get_raw_alerts():
    # get the list of investigations from InsightIDR
    response = requests.get(insightidr_url, headers=insightidr_headers)

    if response.status_code != 200:
        logger.error(f"Failed to get investigations from InsightIDR: {response.reason}")
        return None

    # parse the response and return the list of investigations
    investigations = response.json()['data']
    # Filter out the alerts based on priority_levels
    investigations = [alert for alert in investigations if alert['priority'] in priority_levels]
    return investigations

def format_alerts(alerts):
    # format the alerts into a payload that Google Chat can read
    message = ''
    cards = []
    for alert in alerts:
        priority = alert.get('priority')
        created_time = alert['created_time']
        title = alert['title']
        url = alert.get('url', '')  # get the 'url' value, or use an empty string if it's not present
        message += f"Created Time: {created_time}\n"
        message += f"Priority: {priority}\n"
        message += f"Title: {title}\nURL: {url}\n\n"
        card = {
            "header": {
                "title": title,
                "subtitle": f"Created Time: {created_time}"
            },
            "sections": [
                {
                    "widgets": [
                        {
                            "textParagraph": {
                                "text": f"Priority: {priority}"
                            }
                        },
                        {
                            "buttons": [
                                {
                                    "textButton": {
                                        "text": "View in IDR",
                                        "onClick": {
                                            "openLink": {
                                                "url": url
                                            }
                                        }
                                    }
                                }
                            ]
                        }
                    ]
                }
            ]
        }
        cards.append(card)

    payload = {
        "text": message,
        "cards": cards
    }

    return payload, cards

def save_formatted_alerts(payload):
    # save the formatted alerts to a file
    with open(formatted_alerts_file, 'w') as f:
        json.dump(payload, f, indent=4)
    logger.info(f"{len(payload['cards'])} formatted alerts saved to {formatted_alerts_file}")

def send_alerts_to_chat(payload, alert_rrns, sent_alert_rrns):
    global sent_alert_rrns_file
    # send the formatted alerts to Google Chat
    webhook_url = config['google_chat']['webhook_url']
    headers = {'Content-Type': 'application/json; charset=UTF-8'}
    response, content = http_obj.request(
        uri=webhook_url,
        method='POST',
        body=json.dumps(payload),
        headers=headers)

    if response.status == 200:
        logger.info(f"{len(alert_rrns)} alerts sent successfully to Google Chat")
        # add the RRNs of the sent alerts to the set of already-sent alert RRNs
        sent_alert_rrns.update(alert_rrns)
        # write the updated set of already-sent alert RRNs to the file
        with open(sent_alert_rrns_file, 'w') as f:
            f.writelines([rrn + '\n' for rrn in sent_alert_rrns])
    else:
        logger.error(f"Failed to send alerts to Google Chat: {response.reason}")

def main():
    global sent_alert_rrns_file

    # read the RRNs of already-sent alerts from the file, if it exists
    sent_alert_rrns = set()
    sent_alert_rrns_file = 'sent_alert_rrns.txt'
    if os.path.isfile(sent_alert_rrns_file):
        with open(sent_alert_rrns_file, 'r') as f:
            for line in f:
                sent_alert_rrns.add(line.strip())

    # get the list of raw alerts from InsightIDR
    raw_alerts = get_raw_alerts()
    if raw_alerts is not None:
        # save the raw alerts to a file
        with open(raw_alerts_file, 'a') as f:
            json.dump(raw_alerts, f, indent=4)
        logger.info(f"{len(raw_alerts)} raw alerts downloaded to {raw_alerts_file}")
    else:
        logger.warning("No raw alerts found.")

    # read the RRNs of the last sent alerts from the file, if it exists
    last_sent_alert_rrns = []
    last_sent_alert_rrns_file = 'last_sent_alert_rrns.txt'
    if os.path.isfile(last_sent_alert_rrns_file):
        with open(last_sent_alert_rrns_file, 'r') as f:
            last_sent_alert_rrns = [line.strip() for line in f]

    # filter the alerts to exclude already-sent alerts
    new_alerts = [alert for alert in raw_alerts if alert['rrn'] not in sent_alert_rrns and alert['rrn'] not in last_sent_alert_rrns]
    logger.info(f"{len(new_alerts)} new alerts found after filtering")


    if new_alerts:
        logger.info(f"{len(new_alerts)} new alerts found.")
        # format the new alerts into a payload that Google Chat can read
        payload, cards = format_alerts(new_alerts)

        # send the formatted alerts to Google Chat
        sent_alert_rrns_before = set(sent_alert_rrns)  # initialize sent_alert_rrns_before with the current value of sent_alert_rrns
        send_alerts_to_chat(payload, [alert['rrn'] for alert in new_alerts], sent_alert_rrns)

        # check if any new alerts were actually sent
        sent_alert_rrns_after = set(sent_alert_rrns)
        if sent_alert_rrns_after > sent_alert_rrns_before:
            logger.info(f"{len(new_alerts)} new alerts sent successfully to Google Chat")
        else:
            logger.warning("No new alerts sent to Google Chat.")
    else:
        logger.info("No new alerts found.")


while True:
    main()
    time.sleep(60)
