# Slack channel support to post messages to slack

class SlackBot:
    SLACK_TOKEN = "<slack-token>"
    SLACK_CHANNEL = "<slack-channel>"

    def __init__(self, channel):
        self.channel = channel

    def send_mess(self, message):
        message = f"{message}"
        return [{"type": "section", "text": {"type": "mrkdwn", "text": message}},]

    def get_message_payload(self, text):
        return {
            "channel": self.channel,
            "blocks": [
                *self.send_mess(message=text),
            ],
        }
