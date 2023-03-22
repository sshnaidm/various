import os
import telebot
import openai

DEBUG = False
FATHER_BOT_TOKEN = os.environ.get("FATHER_BOT_TOKEN")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
if not FATHER_BOT_TOKEN or not OPENAI_API_KEY:
    raise Exception("FATHER_BOT_TOKEN and OPENAI_API_KEY must be set as environment variables")

# Set up the Telegram bot
bot = telebot.TeleBot(FATHER_BOT_TOKEN, parse_mode="MARKDOWN")

# Set up the OpenAI API key
openai.api_key = OPENAI_API_KEY


# Define a function to handle messages sent to the bot
@bot.message_handler(commands=["start", "help"])
def send_welcome(message):
    bot.reply_to(message, "Starting conversation.")


@bot.message_handler(func=lambda _: True)
def handle_message(message):
    tokens_ai = 500
    temperature_ai = 0.4
    try:
        prompt = message.text
        # Adjust tokens and temperature if specified in the prompt
        # Example: "my question goes here tokens: 100 temp: 0.5 and can contuinue question"
        if "tokens:" in prompt:
            tokens = prompt.split("tokens:")[1].split()[0].strip()
            if tokens.isdigit():
                tokens_ai = int(tokens)
                prompt = prompt.replace("tokens:%s" % tokens, "").replace("tokens: %s" % tokens, "")
        if "temp:" in prompt:
            temperature = prompt.split("temp:")[1].split()[0].strip()
            if temperature.replace(".", "", 1).isdigit():
                temperature_ai = float(temperature)
                prompt = prompt.replace("temp:%s" % temperature, "").replace("temp: %s" % temperature, "")
        prompt = f"{prompt}. Use ``` for code."  # Always remind bot to use ``` for code

        # Send the user's message to OpenAI API
        response = openai.Completion.create(
            # "code-davinci-002", "text-davinci-003", "davinci", whatever
            model="text-davinci-003",
            prompt=prompt,
            max_tokens=tokens_ai,
            n=1,
            stop=None,
            temperature=temperature_ai,
        )
        if DEBUG:
            print(f"You: {prompt}")
            print(response)

        # Getthe answer from the OpenAI API response
        answer = response.choices[0].text.strip()
        # Discover the reason for the bot's end of conversation
        # If the bot stopped because it reached the max tokens, add a footnote (finish: length)
        finsih_reason = response.choices[0].finish_reason
        finish = f"finish: {finsih_reason}  " if finsih_reason and finsih_reason != "stop" else ""
        # Add the total tokens used and the time it took to the answer
        foot = f"\n\n summary:: {finish}total tokens: {response.usage.total_tokens} time:{response._response_ms/1000}s"
        answer += foot

        # Send the answer back to the user
        bot.reply_to(message, answer)

    except Exception as e:
        # If there is an error, send a message to the user
        bot.reply_to(message, f"Exception occurred: {e}")


# Start the bot
bot.polling()
