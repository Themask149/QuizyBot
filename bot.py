import discord

from dotenv import load_dotenv
import os
import pathlib
import random 
import glob
import re
import html

load_dotenv()
# Create an instance of a Client. This client represents your bot.
intents = discord.Intents.default()
intents.message_content = True

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

	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)
		files_path=glob.glob("./Quizypedia_*.txt")
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
				with open(self.dict_files[message.content[1:]], "r") as file:
					lines = file.readlines()
					random_line=lines[random.randint(0,len(lines)-1)].split("\t")
					reponse=random_line[0].strip()
					theme=random_line[1].strip()
					max_index=random_line.index("")
					random_indice=decode_html_entities(random_line[random.randint(2,max_index-1)])
					has_url,url=extract_url(random_indice)
					await message.channel.send(f"Voici une question du thème: {theme}\nTrouvez la réponse avec cet indice:\n")
					if has_url:
						random_indice=url
						embed=discord.Embed(title="Indice")
						embed.set_image(url=url)
						await message.channel.send(embed=embed)
					else:
						await message.channel.send(random_indice.strip())
					await message.channel.send(f"\nLa réponse (en spoiler) est: ||{reponse}||")

client = MyClient(intents=intents)

client.run(os.getenv('TOKEN'))
