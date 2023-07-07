
# How to Setup Script

1: Download the script
Download the script from the source and save it in a folder of your choice.

2: Install the required packages
The script uses some packages that may not be installed on your machine. Please install the required packages using the following command:

`pip install -r requirements.txt`

3: Set up the configuration file
Create a file named "config.ini" in the same folder as the script and add the following content to it:
```
[insightidr]
api_key = api_key_here
region = what_region_your_instance_is(us1, us2, eu1, etc etc)

[google_chat]
webhook_url = google_workspace_webhook_url_here
```

Replace "api_key_here" with your InsightIDR API key and "what_region_your_instance_is" with the region where your InsightIDR instance is located. Replace "google_workspace_webhook_url_here" with the webhook URL of the Google Chat room where you want to receive the alerts, additionally with the webhook it will container a % neard the end, for the config.ini to process it properly it must be doubled. See example webhook url below:

`https://chat.googleapis.com/v1/spaces/AAAAuigBr7m/messages?key=EXjeKbJwJ8aEDZaJ0akjKzSk-GOfNw5MTcYhhyxFK&token=c6ZAKYT9v9XxiqBJcaMmG5WUtfxib6PjLsQV7zkzSBt%%3D`

4: Set up the service account
To use the script, you need to set up a service account with appropriate permissions in your InsightIDR instance. Please follow the instructions on the Rapid7 website to set up the service account and grant it the necessary permissions.

5: Set up the systemd service
Create a file named "insightidr_alerts.service" in the "/etc/systemd/system/" directory and add the following content to it:
```
[Unit]
Description=InsightIDR Alerts Service
After=network.target

[Service]
User=place_service_account_here
ExecStart=/usr/bin/python3 /opt/r7scripts/gchatalert/IDR_Alerts_to_Google_chat.py
WorkingDirectory=/opt/r7scripts/gchatalert
Restart=always

[Install]
WantedBy=multi-user.target
```

Replace "place_service_account_here" with the name of the service account you created in Step 4. Replace "/path/to/script/folder" with the path to the folder where you saved the script.

6: Go to home page of InsightIDR and copy the random letters and numbers in the URL bar after

`https://us2.idr.insight.rapid7.com/op/`

It will look something like 390BEBE96E1D4DE4A51B#

7: Open the script and under the format_alerts function look for

`url = f"https://{region}.idr.insight.rapid7.com/op/"place your companyid here"#/investigations/{id_v1}" if id_v1 else ''`

Replace the "place your companyid here" your companyid. Shoud look like this after

`url = f"https://{region}.idr.insight.rapid7.com/op/390BEBE96E1D4DE4A51B#/investigations/{id_v1}" if id_v1 else ''`

6: Start the service
Start the service using the following command:

`sudo systemctl enable insightidr_alerts && sudo systemctl start insightidr_alerts`

The script will run continuously in the background and will check for new alerts every minute. The alerts will be sent to the Google Chat room configured in the "config.ini" file.

## How to Generate an API Key for Rapid7 Insight Platform
API keys are used to authenticate access to the Rapid7 Insight platform APIs. To generate an API key, follow these steps:

1. Log in to the Rapid7 Insight platform.

2. Navigate to the "API & Integrations" page.

3. Click the "Create API Key" button.

4. In the "Create API Key" dialog, enter a name and description for the API key.

5. Select the permissions that the API key should have. The available permissions are "Read" and "Write."

6. Click the "Create" button to generate the API key.

7. Copy the API key and save it in a secure location.

Note: Once you leave the "Create API Key" dialog, you will not be able to access the API key again. Make sure to copy the API key and save it in a secure location.

## Creating Webhook for Google Chat Space. 

**Note: You'll Require Admin for the Chat Space to Generate a Webhook**

1. In a web browser, open Google Chat.

2. Go to the space to which you want to add a webhook.

3. At the top, next to space title, click Down Arrow arrow_drop_down > Apps & integrations.

4. Click Manage webhooks.

5. If this space already has other webhooks, click Add another. Otherwise, skip this step.

6. For Name, enter "IDR_Alerts".

7. For Avatar URL, this URL is the IDR Icon https://lh3.googleusercontent.com/proxy/yw94y6A_XHjPSbBAECseM4a_QwZ600PglW9NpUYKT-_k-AzijOL5SPDKwvX_3s3w41HU9RVSXCJHK8yqwxWPJ7NlMZ0SDn8-

8. Click SAVE.

9. To copy the full webhook URL, click content_copy Copy.

10. Click outside the box to close the Incoming webhooks dialog.
