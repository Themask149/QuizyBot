import asyncio
import discord

from dotenv import load_dotenv
import os
import pathlib
import random 
import glob
import re
import html
from request import *
from datetime import datetime, timedelta
from thefuzz import fuzz
from thefuzz import process

load_dotenv()
# Create an instance of a Client. This client represents your bot.
intents = discord.Intents.default()
intents.message_content = True

QUIZY="https://www.quizypedia.fr/"
Threshold=80
Message_Remarque="Merci pour ta remarque ! N'hésite pas à l'indiquer directement sur le site sur la page du thème pour que Grégory n'oublie pas de la prendre en compte !"
Message_Essentiels="Je pense que la liste des thèmes essentiels te sera très utile pour réviser ! Voici le lien: https://docs.google.com/document/d/1r3EIBfwiPdSDO15Fenb9TfHP-IaDEp67-b7ftIIiJ8Q/"
Message_Duels="Comment faire des duels ? Qu'est-ce qu'un g8 ? Est-ce que ça a un rapport avec le G7 ??? 🤔\nNe t'inquiète pas toutes tes réponses sont ici : https://www.youtube.com/watch?v=OyqzWTvaWdQ"

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

def verify_response(response, correct_response):
	response = response.strip().lower()
	correct_response = correct_response.strip().lower()
	return fuzz.ratio(response, correct_response) > Threshold


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

	def presentation_question(self,q,hints,responses):
		strings=[f"__{q}__"]
		for h,r in zip(hints,responses):
			strings.append(f"\n\n{miseenformehint(h)}\n\nLa réponse (en spoiler) est: ||{r}||\n"+'-'*20+'\n')
		return strings
	
	def parse_options(self,content):
		nb_pattern = re.search(r'nb:(\d+)', content)
		delai_pattern = re.search(r'delai:(\d+)', content)
		difficulty_pattern = re.search(r'difficulty:(\w+)', content)
		num_questions = 1
		time_to_wait = 20 
		difficulty = "essentiel"
		
		if nb_pattern:
			num_questions = int(nb_pattern.group(1))
		if delai_pattern:
			time_to_wait = int(delai_pattern.group(1))
		if difficulty_pattern:
			if difficulty_pattern.group(1) in ["essentiel", "hard"]:
				difficulty = difficulty_pattern.group(1)
		
		return num_questions, time_to_wait,difficulty
	
	async def present_question(self, message,theme,nb=1,delai=20,diff="essentiel"):
		getQuizzes(self.session,'https://www.quizypedia.fr/quiz/Lieux%20de%20collections%20(1)/')
		for _ in range(nb):
			if diff=="essentiel":
				file_path = self.dict_files.get(theme)
				if not file_path:
					await message.channel.send(f"Le thème '{theme}' n'existe pas.")
					return
				url=random.choice(extractUrl(file_path))
				quizzes=getQuizzes(self.session,url)
				url=QUIZY[:-1]+random.choice(quizzes)
				idurl=getQuizId(self.session,url)
				quiz=getQuiz(self.session,url,idurl)
				t,q,h,r=extractQuestion(quiz)
			elif diff=="hard":
				quiz=getRandomQuiz(self.session)
				t,q,h,r=extractQuestion(quiz)
			
			hint,response=randomQuestion(h,r)
			hint=miseenformehint(hint)
			response=miseenformeresponse(response)
			start_time = datetime.now()  
			end_time = start_time + timedelta(seconds=delai) 
			def check(m):
				return m.channel == message.channel and datetime.now() < end_time
			await message.channel.send(f"Voici une question du thème:\n# {t}\n\n__{q}__\n{hint}\n\nVous avez {delai}s pour répondre.")
			try:
				while datetime.now() < end_time:
					# Wait for the next message that meets the check function
					new_message = await client.wait_for('message', check=check, timeout=(end_time - datetime.now()).total_seconds())
					if verify_response(new_message.content, response):
						await new_message.add_reaction('👍')  # React with a thumbs up emoji
					else:
						await new_message.add_reaction('👎')
			except asyncio.TimeoutError:
				pass 
			await message.channel.send(f"\n\nLa réponse (en spoiler) est: ||{response}||")
			while datetime.now() < end_time+timedelta(seconds=2):
				pass


	async def handle_quiz_command(self, message, url):
		idurl=getQuizId(self.session,url)
		if not idurl:
			await message.channel.send("L'url n'est pas valide.")
			return
		quiz=getQuiz(self.session,url,idurl)
		t,q,h,r=extractQuestion(quiz)
		strings=self.presentation_question(q,h,r)
		await message.channel.send(f"Voici une question du thème:\n# {t}")
		for string in strings:
			await message.channel.send(string)
	
	async def on_ready(self):
		print(f'We have logged in as {self.user}')

	async def on_message(self, message):
		if message.author == self.user:
			return

		if message.content.startswith('!remarque'):
			await message.channel.send(Message_Remarque)
			await message.channel.send(file=discord.File('remarque.png'))
			return

		if message.content.startswith('!essentiels'):
			await message.channel.send(Message_Essentiels)
			return
		
		if message.content.startswith('!duel'):
			await message.channel.send(Message_Duels)
			return
		
		if message.content.startswith('!hello'):
			await message.channel.send('Hello!')

		if message.content.startswith('!quiz'):
			parts = message.content.split()
			if len(parts) == 2:
				has_url,url = extract_url(parts[1])
				if has_url:
					await self.handle_quiz_command(message, url)
		
		if message.content.startswith('!themes'):
			await message.channel.send('Voici les thèmes disponibles: \n' + "\n".join(self.dict_files.keys())+"\nrandom")
		
		if message.content.startswith('!random'):
			
			nb,delai,diff=self.parse_options(message.content)
			print(f"Asking {nb} questions for {delai}s with difficulty {diff}")
			await self.present_question(message,random.choice(list(self.dict_files.keys())),nb=nb,delai=delai,diff=diff)

		if message.content.startswith('!g8'):
			for theme in self.dict_files.keys():
				await self.present_question(message,theme,nb=1,delai=20,diff="essentiel")

		decomp=message.content.split()
		if len(decomp)>0 and decomp[0][0]=='!':
			decomp=decomp[0][1:]
			print(decomp)
			if f"{decomp}" in self.dict_files.keys():
				nb,delai,diff=self.parse_options(message.content)
				if diff=="hard":
					await message.channel.send(f"Le mode hard n'est pas disponible pour un thème spécifique.")
				print(f"{decomp} : Asking {nb} questions for {delai}s with difficulty {diff}")
				await self.present_question(message,f"{decomp}",nb=nb,delai=delai,diff=diff)

client = MyClient(intents=intents)

client.run(os.getenv('TOKEN'))
