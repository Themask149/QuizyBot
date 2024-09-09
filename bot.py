import discord

from dotenv import load_dotenv
import os
import pathlib
import random 
import glob
import re
import html
from request import *

load_dotenv()
# Create an instance of a Client. This client represents your bot.
intents = discord.Intents.default()
intents.message_content = True

QUIZY="https://www.quizypedia.fr/"


def extract_url(string):
	has_url=False
	url=""
	url_pattern = re.compile(r'https?://[^\s"\'<>]+', re.IGNORECASE)
	urls = url_pattern.findall(string)
	if len(urls)>0:
		has_url=True
		url=urls[0]
	return has_url,url

def decode_html_entities(text):
    # Decode HTML entities
    return html.unescape(text)

class MyClient(discord.Client):

	dict_files={}
	session=None

	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)
		files_path=glob.glob("./Quizypedia_*.txt")
		self.session = requests.Session()
		for file in files_path:
			self.dict_files[file.split("_")[1].split(".")[0]]=file
		print("Files loaded: ",self.dict_files)

	
	async def on_ready(self):
		print(f'We have logged in as {self.user}')

	async def on_message(self, message):
		if message.author == self.user:
			return

		if message.content.startswith('!hello'):
			await message.channel.send('Hello!')
		
		if message.content.startswith('!quiz'):
			await message.channel.send('Voici les thèmes disponibles: \n' + "\n".join(self.dict_files.keys()))

		if len(message.content.split())==1:
			if f"{message.content[1:]}" in self.dict_files.keys():
				url=random.choice(extractUrl(self.dict_files[f"{message.content[1:]}"]))
				quizzes=getQuizzes(self.session,url)
				url=QUIZY[:-1]+random.choice(quizzes)
				idurl=getQuizId(self.session,url)
				quiz=getQuiz(self.session,url,idurl)
				t,q,h,r=extractQuestion(quiz)
				hint,response=randomQuestion(h,r)
				hint=miseenformehint(hint)
				await message.channel.send(f"Voici une question du thème:\n# {t}\n\n__{q}__\n")
				await message.channel.send(f"{hint}")
				await message.channel.send(f"\n\nLa réponse (en spoiler) est: ||{response}||")

client = MyClient(intents=intents)

client.run(os.getenv('TOKEN'))
