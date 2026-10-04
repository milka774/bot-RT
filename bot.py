"""
Bot Discord multifonction (discord.py 2.x, commandes slash)

Fonctions :
- Verrouiller / déverrouiller un salon ou tout le serveur
- Mode lent (slowmode)
- Donner / retirer / créer des rôles
- Modifier les permissions d'un rôle sur un salon
- Modération : kick, ban, unban, timeout, clear, warn
- Message de bienvenue + rôle automatique
- Infos : userinfo, serverinfo, avatar
- Extras : sondage, annonce, pile ou face, dé

Installation :
    pip install -U discord.py python-dotenv
Fichier .env à côté du script :
    DISCORD_MTU1NjMwODU0OTg2MzQ4MTM0NA.G528ME.IyP_EyE58VpNstJgs--UIJbDEFo6V4ROoLiZwI
Lancement :
    python bot.py
"""

import os
import json
import random
from datetime import timedelta

import discord
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")
DATA_FILE = "data.json"


# ----------------------------------------------------------------------
# Petit stockage JSON (avertissements + config de bienvenue)
# ----------------------------------------------------------------------
def load_data() -> dict:
    if not os.path.exists(DATA_FILE):
        return {"warns": {}, "welcome": {}}
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_data(data: dict) -> None:
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


# ----------------------------------------------------------------------
# Bot
# ----------------------------------------------------------------------
intents = discord.Intents.default()
intents.members = True  # à activer aussi dans le portail développeur


class MonBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self):
        await self.tree.sync()
        print("Commandes slash synchronisées.")


bot = MonBot()


@bot.event
async def on_ready():
    print(f"Connecté en tant que {bot.user} (id: {bot.user.id})")
    await bot.change_presence(activity=discord.Game(name="/aide"))


# ----------------------------------------------------------------------
# Utilitaires
# ----------------------------------------------------------------------
def role_gerable(interaction: discord.Interaction, role: discord.Role) -> str | None:
    """Retourne un message d'erreur si le rôle ne peut pas être géré, sinon None."""
    guild = interaction.guild
    if role.is_default() or role.managed:
        return "Ce rôle ne peut pas être attribué manuellement."
    if role >= guild.me.top_role:
        return "Mon rôle doit être **au-dessus** de ce rôle dans la liste des rôles du serveur."
    if interaction.user != guild.owner and role >= interaction.user.top_role:
        return "Tu ne peux pas gérer un rôle supérieur ou égal au tien."
    return None


def membre_gerable(interaction: discord.Interaction, member: discord.Member) -> str | None:
    guild = interaction.guild
    if member == guild.owner:
        return "Impossible d'agir sur le propriétaire du serveur."
    if member.top_role >= guild.me.top_role:
        return "Mon rôle est trop bas pour agir sur ce membre."
    if interaction.user != guild.owner and member.top_role >= interaction.user.top_role:
        return "Ce membre a un rôle supérieur ou égal au tien."
    return None


# ----------------------------------------------------------------------
# 1) Verrouillage des salons
# ----------------------------------------------------------------------
@bot.tree.command(name="lock", description="Verrouille un salon (plus personne ne peut écrire)")
@app_commands.describe(salon="Salon à verrouiller (par défaut : celui-ci)", raison="Raison")
@app_commands.guild_only()
@app_commands.default_permissions(manage_channels=True)
@app_commands.checks.has_permissions(manage_channels=True)
async def lock(interaction: discord.Interaction, salon: discord.TextChannel = None, raison: str = "Aucune raison"):
    salon = salon or interaction.channel
    everyone = interaction.guild.default_role
    ow = salon.overwrites_for(everyone)
    ow.send_messages = False
    ow.add_reactions = False
    ow.create_public_threads = False
    await salon.set_permissions(everyone, overwrite=ow, reason=f"{interaction.user} : {raison}")
    await interaction.response.send_message(f"🔒 {salon.mention} est verrouillé. Raison : {raison}")


@bot.tree.command(name="unlock", description="Déverrouille un salon")
@app_commands.describe(salon="Salon à déverrouiller (par défaut : celui-ci)")
@app_commands.guild_only()
@app_commands.default_permissions(manage_channels=True)
@app_commands.checks.has_permissions(manage_channels=True)
async def unlock(interaction: discord.Interaction, salon: discord.TextChannel = None):
    salon = salon or interaction.channel
    everyone = interaction.guild.default_role
    ow = salon.overwrites_for(everyone)
    ow.send_messages = None
    ow.add_reactions = None
    ow.create_public_threads = None
    await salon.set_permissions(everyone, overwrite=ow, reason=f"Déverrouillé par {interaction.user}")
    await interaction.response.send_message(f"🔓 {salon.mention} est déverrouillé.")


@bot.tree.command(name="lockdown", description="Verrouille TOUS les salons textuels du serveur")
@app_commands.guild_only()
@app_commands.default_permissions(administrator=True)
@app_commands.checks.has_permissions(administrator=True)
async def lockdown(interaction: discord.Interaction):
    await interaction.response.defer()
    everyone = interaction.guild.default_role
    compteur = 0
    for salon in interaction.guild.text_channels:
        try:
            ow = salon.overwrites_for(everyone)
            ow.send_messages = False
            await salon.set_permissions(everyone, overwrite=ow, reason=f"Lockdown par {interaction.user}")
            compteur += 1
        except discord.Forbidden:
            pass
    await interaction.followup.send(f"🚨 Lockdown activé : {compteur} salons verrouillés.")


@bot.tree.command(name="unlockdown", description="Déverrouille TOUS les salons textuels du serveur")
@app_commands.guild_only()
@app_commands.default_permissions(administrator=True)
@app_commands.checks.has_permissions(administrator=True)
async def unlockdown(interaction: discord.Interaction):
    await interaction.response.defer()
    everyone = interaction.guild.default_role
    compteur = 0
    for salon in interaction.guild.text_channels:
        try:
            ow = salon.overwrites_for(everyone)
            ow.send_messages = None
            await salon.set_permissions(everyone, overwrite=ow, reason=f"Fin du lockdown par {interaction.user}")
            compteur += 1
        except discord.Forbidden:
            pass
    await interaction.followup.send(f"✅ Lockdown levé : {compteur} salons déverrouillés.")


@bot.tree.command(name="slowmode", description="Définit le mode lent d'un salon (0 pour désactiver)")
@app_commands.describe(secondes="Délai entre deux messages (0 à 21600)", salon="Salon concerné")
@app_commands.guild_only()
@app_commands.default_permissions(manage_channels=True)
@app_commands.checks.has_permissions(manage_channels=True)
async def slowmode(interaction: discord.Interaction, secondes: app_commands.Range[int, 0, 21600], salon: discord.TextChannel = None):
    salon = salon or interaction.channel
    await salon.edit(slowmode_delay=secondes)
    msg = "désactivé" if secondes == 0 else f"réglé sur {secondes}s"
    await interaction.response.send_message(f"🐢 Mode lent {msg} dans {salon.mention}.")


# ----------------------------------------------------------------------
# 2) Rôles et permissions
# ----------------------------------------------------------------------
PRESETS = {
    "membre": discord.Permissions(
        view_channel=True, send_messages=True, read_message_history=True,
        add_reactions=True, embed_links=True, attach_files=True,
        connect=True, speak=True, use_voice_activation=True,
    ),
    "modo": discord.Permissions(
        view_channel=True, send_messages=True, read_message_history=True,
        add_reactions=True, embed_links=True, attach_files=True,
        connect=True, speak=True, manage_messages=True, kick_members=True,
        moderate_members=True, mute_members=True, deafen_members=True,
    ),
    "admin": discord.Permissions(administrator=True),
}


@bot.tree.command(name="role_add", description="Donne un rôle à un membre")
@app_commands.guild_only()
@app_commands.default_permissions(manage_roles=True)
@app_commands.checks.has_permissions(manage_roles=True)
async def role_add(interaction: discord.Interaction, membre: discord.Member, role: discord.Role):
    erreur = role_gerable(interaction, role)
    if erreur:
        return await interaction.response.send_message(f"❌ {erreur}", ephemeral=True)
    await membre.add_roles(role, reason=f"Par {interaction.user}")
    await interaction.response.send_message(f"✅ {role.mention} donné à {membre.mention}.")


@bot.tree.command(name="role_remove", description="Retire un rôle à un membre")
@app_commands.guild_only()
@app_commands.default_permissions(manage_roles=True)
@app_commands.checks.has_permissions(manage_roles=True)
async def role_remove(interaction: discord.Interaction, membre: discord.Member, role: discord.Role):
    erreur = role_gerable(interaction, role)
    if erreur:
        return await interaction.response.send_message(f"❌ {erreur}", ephemeral=True)
    await membre.remove_roles(role, reason=f"Par {interaction.user}")
    await interaction.response.send_message(f"✅ {role.mention} retiré à {membre.mention}.")


@bot.tree.command(name="role_create", description="Crée un nouveau rôle avec un preset de permissions")
@app_commands.describe(nom="Nom du rôle", couleur="Couleur hex, ex : #ff8800", preset="Niveau de permissions")
@app_commands.choices(preset=[
    app_commands.Choice(name="Membre (basique)", value="membre"),
    app_commands.Choice(name="Modérateur", value="modo"),
    app_commands.Choice(name="Administrateur", value="admin"),
])
@app_commands.guild_only()
@app_commands.default_permissions(manage_roles=True)
@app_commands.checks.has_permissions(manage_roles=True)
async def role_create(interaction: discord.Interaction, nom: str, preset: app_commands.Choice[str], couleur: str = "#99aab5"):
    if preset.value == "admin" and not interaction.user.guild_permissions.administrator:
        return await interaction.response.send_message("❌ Seul un administrateur peut créer un rôle admin.", ephemeral=True)
    try:
        colour = discord.Colour.from_str(couleur)
    except ValueError:
        return await interaction.response.send_message("❌ Couleur invalide. Exemple : `#ff8800`", ephemeral=True)
    role = await interaction.guild.create_role(
        name=nom, colour=colour, permissions=PRESETS[preset.value],
        reason=f"Créé par {interaction.user}",
    )
    await interaction.response.send_message(f"🎭 Rôle {role.mention} créé (preset **{preset.name}**).")


PERMISSIONS_SALON = [
    app_commands.Choice(name="Voir le salon", value="view_channel"),
    app_commands.Choice(name="Écrire des messages", value="send_messages"),
    app_commands.Choice(name="Lire l'historique", value="read_message_history"),
    app_commands.Choice(name="Ajouter des réactions", value="add_reactions"),
    app_commands.Choice(name="Envoyer des fichiers", value="attach_files"),
    app_commands.Choice(name="Intégrer des liens", value="embed_links"),
    app_commands.Choice(name="Se connecter (vocal)", value="connect"),
    app_commands.Choice(name="Parler (vocal)", value="speak"),
]


@bot.tree.command(name="perm_salon", description="Autorise / interdit une permission à un rôle sur un salon")
@app_commands.describe(salon="Salon concerné", role="Rôle concerné", permission="Permission à modifier", action="Que faire ?")
@app_commands.choices(
    permission=PERMISSIONS_SALON,
    action=[
        app_commands.Choice(name="Autoriser", value="allow"),
        app_commands.Choice(name="Interdire", value="deny"),
        app_commands.Choice(name="Réinitialiser (neutre)", value="reset"),
    ],
)
@app_commands.guild_only()
@app_commands.default_permissions(manage_channels=True)
@app_commands.checks.has_permissions(manage_channels=True)
async def perm_salon(
    interaction: discord.Interaction,
    salon: discord.abc.GuildChannel,
    role: discord.Role,
    permission: app_commands.Choice[str],
    action: app_commands.Choice[str],
):
    valeur = {"allow": True, "deny": False, "reset": None}[action.value]
    ow = salon.overwrites_for(role)
    setattr(ow, permission.value, valeur)
    await salon.set_permissions(role, overwrite=ow, reason=f"Par {interaction.user}")
    await interaction.response.send_message(
        f"🔧 **{permission.name}** → **{action.name}** pour {role.mention} dans {salon.mention}."
    )


# ----------------------------------------------------------------------
# 3) Modération
# ----------------------------------------------------------------------
@bot.tree.command(name="kick", description="Expulse un membre")
@app_commands.guild_only()
@app_commands.default_permissions(kick_members=True)
@app_commands.checks.has_permissions(kick_members=True)
async def kick(interaction: discord.Interaction, membre: discord.Member, raison: str = "Aucune raison"):
    erreur = membre_gerable(interaction, membre)
    if erreur:
        return await interaction.response.send_message(f"❌ {erreur}", ephemeral=True)
    await membre.kick(reason=f"{interaction.user} : {raison}")
    await interaction.response.send_message(f"👢 {membre} a été expulsé. Raison : {raison}")


@bot.tree.command(name="ban", description="Bannit un membre")
@app_commands.guild_only()
@app_commands.default_permissions(ban_members=True)
@app_commands.checks.has_permissions(ban_members=True)
async def ban(interaction: discord.Interaction, membre: discord.Member, raison: str = "Aucune raison"):
    erreur = membre_gerable(interaction, membre)
    if erreur:
        return await interaction.response.send_message(f"❌ {erreur}", ephemeral=True)
    await membre.ban(reason=f"{interaction.user} : {raison}")
    await interaction.response.send_message(f"🔨 {membre} a été banni. Raison : {raison}")


@bot.tree.command(name="unban", description="Débannit un utilisateur grâce à son ID")
@app_commands.guild_only()
@app_commands.default_permissions(ban_members=True)
@app_commands.checks.has_permissions(ban_members=True)
async def unban(interaction: discord.Interaction, user_id: str):
    try:
        user = await bot.fetch_user(int(user_id))
        await interaction.guild.unban(user)
        await interaction.response.send_message(f"✅ {user} a été débanni.")
    except (ValueError, discord.NotFound):
        await interaction.response.send_message("❌ Utilisateur introuvable ou pas banni.", ephemeral=True)


@bot.tree.command(name="timeout", description="Rend un membre muet pendant X minutes")
@app_commands.describe(minutes="Durée (1 à 40320 = 28 jours)")
@app_commands.guild_only()
@app_commands.default_permissions(moderate_members=True)
@app_commands.checks.has_permissions(moderate_members=True)
async def timeout(interaction: discord.Interaction, membre: discord.Member, minutes: app_commands.Range[int, 1, 40320], raison: str = "Aucune raison"):
    erreur = membre_gerable(interaction, membre)
    if erreur:
        return await interaction.response.send_message(f"❌ {erreur}", ephemeral=True)
    await membre.timeout(timedelta(minutes=minutes), reason=f"{interaction.user} : {raison}")
    await interaction.response.send_message(f"🤐 {membre.mention} est muet pendant {minutes} min. Raison : {raison}")


@bot.tree.command(name="untimeout", description="Retire le timeout d'un membre")
@app_commands.guild_only()
@app_commands.default_permissions(moderate_members=True)
@app_commands.checks.has_permissions(moderate_members=True)
async def untimeout(interaction: discord.Interaction, membre: discord.Member):
    await membre.timeout(None)
    await interaction.response.send_message(f"🔊 {membre.mention} peut de nouveau parler.")


@bot.tree.command(name="clear", description="Supprime des messages dans le salon")
@app_commands.describe(nombre="Nombre de messages à supprimer (1 à 100)")
@app_commands.guild_only()
@app_commands.default_permissions(manage_messages=True)
@app_commands.checks.has_permissions(manage_messages=True)
async def clear(interaction: discord.Interaction, nombre: app_commands.Range[int, 1, 100]):
    await interaction.response.defer(ephemeral=True)
    supprimes = await interaction.channel.purge(limit=nombre)
    await interaction.followup.send(f"🧹 {len(supprimes)} messages supprimés.", ephemeral=True)


@bot.tree.command(name="warn", description="Avertit un membre")
@app_commands.guild_only()
@app_commands.default_permissions(moderate_members=True)
@app_commands.checks.has_permissions(moderate_members=True)
async def warn(interaction: discord.Interaction, membre: discord.Member, raison: str):
    data = load_data()
    cle = f"{interaction.guild.id}-{membre.id}"
    data["warns"].setdefault(cle, []).append({"raison": raison, "par": str(interaction.user)})
    save_data(data)
    total = len(data["warns"][cle])
    await interaction.response.send_message(f"⚠️ {membre.mention} averti ({total} avertissement(s)). Raison : {raison}")


@bot.tree.command(name="warns", description="Affiche les avertissements d'un membre")
@app_commands.guild_only()
@app_commands.default_permissions(moderate_members=True)
@app_commands.checks.has_permissions(moderate_members=True)
async def warns(interaction: discord.Interaction, membre: discord.Member):
    data = load_data()
    liste = data["warns"].get(f"{interaction.guild.id}-{membre.id}", [])
    if not liste:
        return await interaction.response.send_message(f"✅ {membre.display_name} n'a aucun avertissement.")
    texte = "\n".join(f"**{i}.** {w['raison']} (par {w['par']})" for i, w in enumerate(liste, 1))
    await interaction.response.send_message(f"⚠️ Avertissements de {membre.mention} :\n{texte}")


# ----------------------------------------------------------------------
# 4) Bienvenue + rôle automatique
# ----------------------------------------------------------------------
@bot.tree.command(name="bienvenue", description="Configure le salon de bienvenue et le rôle automatique")
@app_commands.describe(salon="Salon où envoyer le message", role="Rôle donné automatiquement (optionnel)")
@app_commands.guild_only()
@app_commands.default_permissions(administrator=True)
@app_commands.checks.has_permissions(administrator=True)
async def bienvenue(interaction: discord.Interaction, salon: discord.TextChannel, role: discord.Role = None):
    if role:
        erreur = role_gerable(interaction, role)
        if erreur:
            return await interaction.response.send_message(f"❌ {erreur}", ephemeral=True)
    data = load_data()
    data["welcome"][str(interaction.guild.id)] = {
        "channel": salon.id,
        "role": role.id if role else None,
    }
    save_data(data)
    await interaction.response.send_message(
        f"👋 Bienvenue configuré dans {salon.mention}" + (f" avec le rôle {role.mention}." if role else ".")
    )


@bot.event
async def on_member_join(member: discord.Member):
    conf = load_data()["welcome"].get(str(member.guild.id))
    if not conf:
        return
    if conf.get("role"):
        role = member.guild.get_role(conf["role"])
        if role:
            try:
                await member.add_roles(role, reason="Rôle automatique")
            except discord.Forbidden:
                pass
    salon = member.guild.get_channel(conf["channel"])
    if salon:
        embed = discord.Embed(
            title="👋 Nouveau membre !",
            description=f"Bienvenue {member.mention} sur **{member.guild.name}** !\nNous sommes maintenant {member.guild.member_count} membres.",
            colour=discord.Colour.green(),
        )
        embed.set_thumbnail(url=member.display_avatar.url)
        await salon.send(embed=embed)


# ----------------------------------------------------------------------
# 5) Infos
# ----------------------------------------------------------------------
@bot.tree.command(name="userinfo", description="Infos sur un membre")
@app_commands.guild_only()
async def userinfo(interaction: discord.Interaction, membre: discord.Member = None):
    membre = membre or interaction.user
    roles = [r.mention for r in reversed(membre.roles) if not r.is_default()]
    embed = discord.Embed(title=str(membre), colour=membre.colour)
    embed.set_thumbnail(url=membre.display_avatar.url)
    embed.add_field(name="ID", value=membre.id)
    embed.add_field(name="Compte créé", value=discord.utils.format_dt(membre.created_at, "R"))
    embed.add_field(name="A rejoint", value=discord.utils.format_dt(membre.joined_at, "R"))
    embed.add_field(name="Rôles", value=" ".join(roles[:15]) or "Aucun", inline=False)
    await interaction.response.send_message(embed=embed)


@bot.tree.command(name="serverinfo", description="Infos sur le serveur")
@app_commands.guild_only()
async def serverinfo(interaction: discord.Interaction):
    g = interaction.guild
    embed = discord.Embed(title=g.name, colour=discord.Colour.blurple())
    if g.icon:
        embed.set_thumbnail(url=g.icon.url)
    embed.add_field(name="Membres", value=g.member_count)
    embed.add_field(name="Salons", value=len(g.channels))
    embed.add_field(name="Rôles", value=len(g.roles))
    embed.add_field(name="Propriétaire", value=g.owner.mention if g.owner else "?")
    embed.add_field(name="Créé", value=discord.utils.format_dt(g.created_at, "R"))
    await interaction.response.send_message(embed=embed)


@bot.tree.command(name="avatar", description="Affiche l'avatar d'un membre")
async def avatar(interaction: discord.Interaction, membre: discord.Member = None):
    membre = membre or interaction.user
    embed = discord.Embed(title=f"Avatar de {membre.display_name}")
    embed.set_image(url=membre.display_avatar.url)
    await interaction.response.send_message(embed=embed)


# ----------------------------------------------------------------------
# 6) Extras / inspiration
# ----------------------------------------------------------------------
@bot.tree.command(name="sondage", description="Crée un sondage 👍 / 👎")
async def sondage(interaction: discord.Interaction, question: str):
    embed = discord.Embed(title="📊 Sondage", description=question, colour=discord.Colour.orange())
    embed.set_footer(text=f"Par {interaction.user.display_name}")
    await interaction.response.send_message(embed=embed)
    msg = await interaction.original_response()
    await msg.add_reaction("👍")
    await msg.add_reaction("👎")


@bot.tree.command(name="annonce", description="Envoie une annonce stylée dans un salon")
@app_commands.guild_only()
@app_commands.default_permissions(manage_guild=True)
@app_commands.checks.has_permissions(manage_guild=True)
async def annonce(interaction: discord.Interaction, salon: discord.TextChannel, titre: str, message: str):
    embed = discord.Embed(title=f"📢 {titre}", description=message, colour=discord.Colour.gold())
    await salon.send(embed=embed)
    await interaction.response.send_message("✅ Annonce envoyée.", ephemeral=True)


@bot.tree.command(name="pile_ou_face", description="Lance une pièce")
async def pile_ou_face(interaction: discord.Interaction):
    await interaction.response.send_message(f"🪙 {random.choice(['Pile', 'Face'])} !")


@bot.tree.command(name="de", description="Lance un dé")
async def de(interaction: discord.Interaction, faces: app_commands.Range[int, 2, 1000] = 6):
    await interaction.response.send_message(f"🎲 d{faces} → **{random.randint(1, faces)}**")


@bot.tree.command(name="aide", description="Liste des commandes")
async def aide(interaction: discord.Interaction):
    embed = discord.Embed(title="📖 Commandes", colour=discord.Colour.blurple())
    embed.add_field(name="🔒 Salons", value="`/lock` `/unlock` `/lockdown` `/unlockdown` `/slowmode`", inline=False)
    embed.add_field(name="🎭 Rôles", value="`/role_add` `/role_remove` `/role_create` `/perm_salon`", inline=False)
    embed.add_field(name="🔨 Modération", value="`/kick` `/ban` `/unban` `/timeout` `/untimeout` `/clear` `/warn` `/warns`", inline=False)
    embed.add_field(name="👋 Serveur", value="`/bienvenue` `/annonce` `/serverinfo` `/userinfo` `/avatar`", inline=False)
    embed.add_field(name="🎉 Fun", value="`/sondage` `/pile_ou_face` `/de`", inline=False)
    await interaction.response.send_message(embed=embed, ephemeral=True)


# ----------------------------------------------------------------------
# Gestion globale des erreurs
# ----------------------------------------------------------------------
@bot.tree.error
async def on_app_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    if isinstance(error, app_commands.MissingPermissions):
        msg = "❌ Tu n'as pas la permission d'utiliser cette commande."
    elif isinstance(error, app_commands.BotMissingPermissions):
        msg = "❌ Il me manque des permissions sur ce serveur."
    else:
        msg = f"❌ Une erreur est survenue : {error}"
        print(error)
    if interaction.response.is_done():
        await interaction.followup.send(msg, ephemeral=True)
    else:
        await interaction.response.send_message(msg, ephemeral=True)


if __name__ == "__main__":
    if not TOKEN:
        raise SystemExit("Token manquant : crée un fichier .env avec DISCORD_TOKEN=...")
    bot.run(TOKEN)