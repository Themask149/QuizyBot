import asyncio
import glob
import html
import io
import os
import re
import requests
import urllib.parse
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import discord
from discord.ext import commands, tasks
from dotenv import load_dotenv
from thefuzz import fuzz


from request import *

load_dotenv()

# Global constants and messages
QUIZY = os.environ.get("QUIZY", "https://www.quizypedia.fr/")
#Params pour check socre et diag server
TODAY_RANKING_ENDPOINT = "getTodayRankingsEndpoint/"
DDJ_ENDPOINT = "defi-du-jour/"
# Valeurs de Prod par défaut si on ne surcharge pas le .env
DDJ_CHANNEL_ID = int(os.environ.get("DDJ_CHANNEL_ID", 1195139115566514289))
MODERATOR_CHANNEL_ID = int(os.environ.get("MODERATOR_CHANNEL_ID", 1282010309262835787))
# Id de Romain
ADMIN_USER_ID = int(os.environ.get("ADMIN_USER_ID", 1199674694362730578))
# Id de Greg
ADMIN_DDJ_USER_ID = int(os.environ.get("ADMIN_DDJ_USER_ID", 446041323452235777))


last_announced_user = None
last_flagged_user = None
should_warn_admin = True
Threshold = 80

with open("top_players.txt", "r") as file:
	top_users_whitelist = [line.strip() for line in file if line.strip()]


Message_Remarque = ("Merci pour ta remarque ! N'hésite pas à l'indiquer directement sur le site sur la page du thème "
					"pour que Grégory n'oublie pas de la prendre en compte !")

Message_Essentiels = ("Je pense que la liste des thèmes essentiels te sera très utile pour réviser ! Tu peux les retrouver dans l'onglet **Essentiels** de la page d'accueil.\n"
					  "Une fois que tu as choisi un thème, nous avons placé un point d'exclamation bleu dans un cercle blanc pour identifier les quiz à jouer en priorité.")

Message_Duels = ("Comment faire des duels ? Qu'est-ce qu'un g8 ? Est-ce que ça a un rapport avec le G7??? 🤔\n"
				 "Ne t'inquiète pas toutes tes réponses sont ici : https://www.youtube.com/watch?v=OyqzWTvaWdQ")
Message_Aide = (
	"**Voici la liste des commandes disponibles :**\n\n"
	"**!remarque**\n→ Tuto pour signaler une remarque.\n\n"
	"**!essentiels**\n→ Fournit le lien vers la liste des thèmes essentiels (pratique pour réviser).\n\n"
	"**!duel**\n→ Explique brièvement comment organiser des duels et donne un lien vers un tutoriel.\n\n"
	"**!quiz <URL du quiz>**\n→ Affiche les questions issues du quiz dont l’URL est fournie.\n\n"
	"**!themes**\n→ Liste tous les thèmes actuellement disponibles pour le bot.\n\n"
	"**!random [nb:x] [delai:y] [difficulty:essentiel|hard]**\n→ Choisit un thème aléatoire et pose x questions (1 par défaut) "
	"avec un délai de réponse y (20 par défaut). Par défaut, on pioche seulement dans les essentiels mais on peut préciser un paramètre "
	"pour piocher parmi tous les quiz\n   • Exemples : `!random nb:3 delai:15` ou `!random nb:2 delai:10`\n\n"
	"**!g8**\n→ Pose une question de chaque thème (mode essentiel).\n\n"
	"**!<theme> [nb:x] [delai:x] [difficulty:essentiel|hard]**\n→ Pose x questions (1 par défaut) sur un thème précis avec un délai "
	"et une difficulté (seul 'essentiel' est disponible pour un thème).\n   • Exemples : `!histoire nb:3 delai:10`"
)

def is_quizy(url: str) -> bool:
	try:
		allowed = urllib.parse.urlsplit(QUIZY)
		candidate = urllib.parse.urlsplit(urllib.parse.unquote(url))
		print(allowed, candidate)
	except Exception:
		return False
	if candidate.scheme != allowed.scheme:
		return False

	if candidate.hostname != allowed.hostname:
		return False

	if candidate.port not in (None, allowed.port):
		return False

	allowed_path = allowed.path.rstrip("/") + "/"
	candidate_path = candidate.path.rstrip("/") + "/"

	if not candidate_path.startswith(allowed_path):
		return False

	return True

	return True

def extract_url(string):
	has_url = False
	url = ""
	url_pattern = re.compile(r'https?://[^\s"\'<>]+', re.IGNORECASE)
	urls = url_pattern.findall(string)
	if urls:
		has_url = True
		url = urllib.parse.quote(urls[0])
	return has_url, url

def decode_html_entities(text):
	return html.unescape(text)

def verify_response(response, correct_response):
	response = response.strip().lower()
	correct_response = correct_response.strip().lower()
	return fuzz.ratio(response, correct_response) > Threshold

# --- Bot Class ---

class MyBot(commands.Bot):
	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)
		
		# Load quiz files into a dictionary (key = theme name)
		self.dict_files = {}
		files_path = glob.glob("./essentiels/Quizypedia_*.txt")
		self.session = requests.Session()
		for file in files_path:
			key = file.split("_")[1].split(".")[0]
			self.dict_files[key] = file
		print("Files loaded:", self.dict_files)
	
	def presentation_question(self, q, hints, responses):
		"""Prepare the question and its hints/responses for display."""
		strings = [f"__{q}__"]
		for h, r in zip(hints, responses):
			strings.append(f"\n\n{miseenformehint(h)}\n\nLa réponse (en spoiler) est: ||{r}||\n{'-'*20}\n")
		return strings
	
	def parse_options(self, content):
		"""Parse options from the message content."""
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
		
		return num_questions, time_to_wait, difficulty
	
	async def present_question(self, message,theme,nb=1,delai=20,diff="essentiel"):
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
					new_message = await self.wait_for('message', check=check, timeout=(end_time - datetime.now()).total_seconds())
					if verify_response(new_message.content, response):
						await new_message.add_reaction('👍') 
					else:
						await new_message.add_reaction('👎')
			except asyncio.TimeoutError:
				pass 
			await message.channel.send(f"\n\nLa réponse (en spoiler) est: ||{response}||")
			while datetime.now() < end_time+timedelta(seconds=2):
				pass

	async def handle_quiz_command(self, message, url):
		"""Handle the !quiz command given a quiz URL."""
		idurl = getQuizId(self.session, url)
		if not idurl:
			await message.channel.send("L'url n'est pas valide.")
			return
		quiz = getQuiz(self.session, url, idurl)
		t, q, h, r = extractQuestion(quiz)
		strings = self.presentation_question(q, h, r)
		await message.channel.send(f"Voici une question du thème:\n# {t}")
		for string in strings:
			await message.channel.send(string)
	
	async def on_ready(self):
		print(f'We have logged in as {self.user}')
	
	async def on_command_error(self, ctx, error):
		"""
		If a command is not found, check if the first word (after '!')
		matches one of your themes. If so, treat it as a theme command.
		"""
		if isinstance(error, commands.CommandNotFound):
			command_name = ctx.message.content.split()[0][1:]
			if command_name in self.dict_files:
				nb, delai, diff = self.parse_options(ctx.message.content)
				if diff == "hard":
					await ctx.send("Le mode hard n'est pas disponible pour un thème spécifique.")
				else:
					print(f"{command_name} : Asking {nb} questions for {delai}s with difficulty {diff}")
					await self.present_question(ctx.message, command_name, nb=nb, delai=delai, diff=diff)
			else:
				await ctx.send("Commande non reconnue.")
		else:
			raise error

# --- Instantiate the Bot ---

intents = discord.Intents.default()
intents.message_content = True

bot = MyBot(command_prefix="!", intents=intents)

# --- Commands using Decorators ---

async def notify(channel_id, message):
	channel = bot.get_channel(channel_id)
	if channel:
		await channel.send(message, suppress_embeds=True)

def is_user_in_top_100(username, rankings):
	return any(entry["user"] == username for entry in rankings[0:100])

@tasks.loop(seconds=60)
async def check_new_record_and_diag_server():
	global last_announced_user
	global last_flagged_user
	global should_warn_admin

	now = datetime.now(ZoneInfo("Europe/Paris"))

	# Éviter d'exécuter entre minuit et 00h15 pour laisser le temps à un premier record propre d'être publié
	if now.hour == 0 and now.minute < 15:
		last_announced_user = None
		last_flagged_user = None
		try:
			response = requests.get(QUIZY + DDJ_ENDPOINT)
			if response.status_code != 200:
				if should_warn_admin:
					await notify(MODERATOR_CHANNEL_ID,
								 f"<@{ADMIN_DDJ_USER_ID}> 🚨 **Le DDJ ne semble pas avoir été publié** 🚨")
				should_warn_admin = False
			else:
				should_warn_admin = True
		except Exception as e:
			if should_warn_admin:
				await notify(MODERATOR_CHANNEL_ID,
							 f"<@{ADMIN_USER_ID}> 🚨 **Quizy ne répond pas** 🚨\n⚠️ Erreur : {str(e)}")
			should_warn_admin = False
		return

	try:
		response = requests.get(QUIZY + TODAY_RANKING_ENDPOINT)
		if response.status_code != 200:
			if should_warn_admin:
				await notify(MODERATOR_CHANNEL_ID,
							 f"<@{ADMIN_USER_ID}> 🚨 **Quizy ne répond pas** 🚨\n⚠️ Code : {response.status_code}")
			should_warn_admin = False
			return

		should_warn_admin = True
		data = response.json()
		rankings = data.get("rankings", [])
		if not rankings:
			return  # Personne n’a encore joué

		top_rank = rankings[0]
		top_rank_user = top_rank.get("user")
		score = top_rank.get("good_responses")
		ddj_id = data.get("id")
		elapsed_time = top_rank.get("elapsed_time")

		if top_rank_user != last_announced_user:

			last_announced_user = top_rank_user

			# Contrôle positif confirmé après suppression du record du tricheur
			if last_flagged_user and not(is_user_in_top_100(last_flagged_user, rankings)):
				await notify(DDJ_CHANNEL_ID,
							 f"🚨 Contrôle positif confirmé pour **{last_flagged_user}** – record retiré.\n"
							 f"✅ On retrouve **{top_rank_user}** en tête du DDJ !"
							 )
				last_flagged_user = None
				return

			message = (
				f"### 🌟 **Nouveau record pour le Défi du Jour n° {ddj_id}** 🌟\n"
				f"👤 **{top_rank_user}**\n"
				f"🏆 **Score**: {score}\n"
				f"⏱️ **Temps**: {elapsed_time} secondes\n"
				f"📑 [**Classement complet**]({QUIZY}{DDJ_ENDPOINT})"
			)

			if isinstance(elapsed_time, (int, float)) and elapsed_time < 60 and top_rank_user not in top_users_whitelist:
				message += (
					f"\n⚠️ **Performance très rapide détectée** – "
					f"<@{ADMIN_USER_ID}> un contrôle antidopage est demandé 🤔"
				)
				last_flagged_user = top_rank_user  # Flag le joueur pour un éventuel contrôle positif

			await notify(DDJ_CHANNEL_ID, message)

	except Exception as e:
		if should_warn_admin:
			await notify(MODERATOR_CHANNEL_ID,
						 f"<@{ADMIN_USER_ID}> 🚨 **Quizy ne répond pas** 🚨\n⚠️ Erreur : {str(e)}")
		should_warn_admin = False

@bot.event
async def on_ready():
	print(f'Bot connecté en tant que {bot.user}')
	check_new_record_and_diag_server.start()

@bot.command(name="remarque")
async def remarque(ctx):
	await ctx.send(Message_Remarque)
	await ctx.send(file=discord.File('images/remarque.png'))

@bot.command(name="essentiels")
async def essentiels(ctx):
	await ctx.send(Message_Essentiels)
	await ctx.send(file=discord.File('images/essentiels.png'))

@bot.command(name="duel")
async def duel(ctx):
	await ctx.send(Message_Duels)

@bot.command(name="aide")
async def aide(ctx):
	await ctx.send(Message_Aide)

@bot.command(name="hello")
async def hello(ctx):
	await ctx.send("Hello!")

@bot.command(name="quiz")
async def quiz(ctx, url: str):
	has_url, extracted_url = extract_url(url)
	if has_url:
		await bot.handle_quiz_command(ctx.message, extracted_url)
	else:
		await ctx.send("Aucune URL valide trouvée.")

@bot.command(name="themes")
async def themes(ctx):
	available = "\n".join(bot.dict_files.keys())
	await ctx.send("Voici les thèmes disponibles: \n" + available + "\nrandom")

@bot.command(name="random")
async def random_command(ctx):
	nb, delai, diff = bot.parse_options(ctx.message.content)
	print(f"Asking {nb} questions for {delai}s with difficulty {diff}")
	theme = random.choice(list(bot.dict_files.keys()))
	await bot.present_question(ctx.message, theme, nb=nb, delai=delai, diff=diff)

@bot.command(name="g8")
async def g8(ctx):
	for theme in bot.dict_files.keys():
		await bot.present_question(ctx.message, theme, nb=1, delai=20, diff="essentiel")
		
@bot.command(name="poll")
async def poll(ctx,type):
	if type=="emile":
		p=discord.Poll(question="Il me manquait...",duration=timedelta(days=1),multiple=True)
		for x in ["La 1re bleue","La 2e bleue","La 3e bleue","La 1re blanche","La 2e blanche","La rouge","Le Banco","Le Super Banco","J'ai gagné 1000 euros Aikeziens"]:
			p.add_answer(text=x)
		await ctx.send(poll=p)


def parse_user_indices(raw: str) -> list[list[str]]:
	"""
	Transforme "a+b;c;def" -> [["a","b"],["c"],["def"]]
	"""
	raw = raw.strip()
	parts = [p.strip() for p in raw.split(";") if p.strip()]
	return [[s.strip() for s in p.split("+") if s.strip()] for p in parts]

def trueIndices(keyslist, indices):
	ind = []
	for liste in indices:
		subind = []
		for string in liste:
			found = False
			for key in keyslist:
				if key.lower().startswith(string.lower()) and not found:
					subind.append(key)
					found = True
			if not found:
				raise ValueError(f"L'indice {string} n'existe pas")
		ind.append(subind)
	return ind

def format_keyslist(keyslist):
	# Affichage lisible dans Discord
	return "\n".join([f"- {k}" for k in keyslist])

async def selectionIndices_discord(ctx, keyslist, *, max_groups=4, timeout=60):
	"""
	Demande à l'utilisateur de choisir les champs dans un ordre.
	Format: "a+b;c;def"
	- ';' = nouveau champ (ou groupe)
	- '+' = fusion / multi-champs dans un même groupe
	Retour: liste de listes de clés validées (comme ton script).
	"""

	def check(m):
		return m.author.id == ctx.author.id and m.channel.id == ctx.channel.id

	await ctx.send(
		"Voici les champs disponibles :\n"
		f"{format_keyslist(keyslist)}\n\n"
		"Donne ton ordre au format `a+b;c;def` (séparateur `;`, fusion avec `+`).\n"
		"Exemples :\n"
		"- `def;lieu` (2 champs)\n"
		"- `lieu+date;def` (lieu et date dans le même champ, def dans un autre)\n"
		"Tape `cancel` pour annuler."
	)

	while True:
		try:
			msg = await ctx.bot.wait_for("message", check=check, timeout=timeout)
		except asyncio.TimeoutError:
			return None  # timeout

		content = msg.content.strip()

		if content.lower() in ("cancel", "stop", "annule"):
			return None

		# Parse
		try:
			raw_indices = parse_user_indices(content)
			chosen = trueIndices(keyslist, raw_indices)
		except Exception as e:
			await ctx.send(
				f"Erreur: {e}\n"
				"Réessaie. Rappel des champs:\n"
				f"{format_keyslist(keyslist)}"
			)
			continue

		# Limite (ta logique: <5)
		if len(chosen) >= 5:
			await ctx.send(
				"Tu as choisi trop d'indices (max 4 groupes).\n"
				f"{format_keyslist(keyslist)}\n"
				"Réessaie."
			)
			continue

		# Affiche le choix et demande confirmation
		pretty = "\n".join([f"{i+1}. {' + '.join(group)}" for i, group in enumerate(chosen)])
		await ctx.send(
			"Voici ce que j’ai compris :\n"
			f"{pretty}\n\n"
			"Confirme (y/n) ?"
		)

		try:
			confirm = await ctx.bot.wait_for("message", check=check, timeout=timeout)
		except asyncio.TimeoutError:
			return None

		if confirm.content.strip().lower() in ("y", "yes", "oui"):
			return chosen

		await ctx.send("Ok, on recommence. Donne ton ordre (ou `cancel`).")

def build_anki_text(final, indices, theme):
	lines = []
	note_test="Ceci est une note test pour vérifier que l'importation fonctionnne; elle sert aussi à s'assurer que tous les champs sont bien remplis; vous pouvez la supprimer;1;2;3"
	lines.append(note_test)
	for card in final:
		parts = []
		for i, group in enumerate(indices):
			if i == 1:
				parts.append(theme)

			chunk = []
			for indice in group:
				if indice == "Image":
					if indice in card and card[indice]:
						chunk.append(f'<img src="{QUIZY+card[indice]}">')
				else:
					if indice in card and card[indice]:
						chunk.append(str(card[indice]))

			parts.append(" ".join(chunk))

		lines.append(";".join(parts))

	return "\n".join(lines)

ALLOWED_CHANNEL_ID = 1352720060732542996
def is_allowed_channel():
    async def predicate(ctx):
        return ctx.channel.id == ALLOWED_CHANNEL_ID
    return commands.check(predicate)


@bot.command(name="ankisator")
@is_allowed_channel()
async def ankisator(ctx, url:str = None):
	if not url:
		await ctx.send("Veuillez fournir une URL.")
		return
	has_url,extracted_url=extract_url(url)
	if not has_url:
		await ctx.send("Aucune URL valide trouvée.")
		return
	if not is_quizy(extracted_url):
		await ctx.send("L'URL fournie n'est pas un lien Quizypedia.")
		return
	theme,fields,fiches=getFiches(url)
	print(theme,fields,fiches)

	if not theme:
		await ctx.send("Impossible de récupérer les informations de la fiche.")
		return

	chosen = await selectionIndices_discord(ctx, fields)
	if chosen is None:
		await ctx.send("Annulé ou timeout.")
		return
	content= build_anki_text(fiches, chosen, theme)
	buffer = io.BytesIO()
	buffer.write(content.encode("utf-8"))
	buffer.seek(0)

	file = discord.File(fp=buffer, filename=f"{theme}.txt")

	await ctx.send("Voici ton fichier Anki :", file=file)

# --- Run the Bot --

bot.run(os.getenv('TOKEN'))
