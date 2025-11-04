from typing import Optional

import discord
from discord import app_commands

from src.utils.functions import libera_ip, slugify, create_daily, create_weekly_report, create_link_user, \
    weekday_default_ptbr_no_feira, create_planning_daily
from src.utils.infisical import get_secret
from src.views.planning_view import ActivitiesView

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

client = discord.Client(intents=intents)

tree = app_commands.CommandTree(client)

@client.event
async def on_ready():
    try:
        await tree.sync()
        print('Comandos globais sincronizados.')
    except Exception as e:
        print(f'Erro ao sincronizar comandos globais: {e}')
    guild_obj = discord.Object(id=get_secret("DISCORD_GUILD_ID"))
    try:
        synced = await tree.sync(guild=guild_obj)
        print(f'Comandos sincronizados na guild {get_secret("DISCORD_GUILD_ID")}: {[c.name for c in synced]}')
    except Exception as e:
        print(f'Erro ao sincronizar comandos: {e}')
    print(f'Bot conectado como {client.user}')

@tree.command(name="libera_ip", description="Libera um IP no servidor.", guild=discord.Object(id=get_secret("DISCORD_GUILD_ID")))
@discord.app_commands.describe(
    ip="IPv4 a ser liberado.",
    regra="Nome da regra no firewall (opcional, se não informado, enviará o nome do usuário que requisitou a liberação)"
)
async def libera_ip_cmd(
        interaction: discord.Interaction,
        ip: str,
        regra: Optional[str] = None,
        env: Optional[str] = "dev"
):
    usuario = interaction.user
    default_rule = getattr(usuario, "display_name", None) or getattr(usuario, "name", None) or "default"
    rule_name = slugify((regra or default_rule).strip())
    channel = interaction.channel_id
    await interaction.response.defer()
    response = await libera_ip(
        rule_name=rule_name,
        channel_id=channel,
        env=env,
        ip=ip
    )
    await interaction.edit_original_response(content=response['message'])

@tree.command(name="daily", description="Mostra os registros de tempo do dia", guild=discord.Object(id=get_secret("DISCORD_GUILD_ID")))
@discord.app_commands.describe(
    date="Data que deseja realizar a daily (formato YYYY-MM-DD). Se não informado usa a data atual."
)
async def daily(interaction: discord.Interaction, date: Optional[str] = None):
    if interaction.user.id != int(get_secret("DISCORD_USER_ID")):
        await interaction.response.send_message("Você não tem permissão para usar este comando.", ephemeral=True)
        return
    await interaction.response.defer(ephemeral=True)
    await create_daily(interaction, date)


@tree.command(name="link_user", description="Vincula o usuário no discord com o usuário no TeamWork", guild=discord.Object(id=get_secret("DISCORD_GUILD_ID")))
@discord.app_commands.describe(
    email="E-mail cadastrado no TeamWork.",
    name="Nome na linha da Planning"
)
async def link_user(interaction: discord.Interaction, email: str, name: str):
    await interaction.response.defer(ephemeral=True)
    mensagens = create_link_user(email, name, interaction.user.id)
    await interaction.edit_original_response(content=mensagens)


@tree.command(name="weekly_report", description="Mostra os registros da semana", guild=discord.Object(id=get_secret("DISCORD_GUILD_ID")))
async def weekly_report(interaction: discord.Interaction):
    if interaction.user.id != int(get_secret("DISCORD_USER_ID")):
        await interaction.response.send_message("Você não tem permissão para usar este comando.", ephemeral=True)
        return
    await interaction.response.defer(ephemeral=True)

    mensagens = create_weekly_report()

    canal = client.get_channel(int(get_secret("DISCORD_CHANNEL_ID")))
    await canal.send(mensagens)
    await interaction.edit_original_response(content="Relatório gerado com sucesso")

@tree.command(
    name="planning_daily",
    description="Monta a planning do dia selecionado, caso não seja selecionado nenhum dia, monta a do dia atual.",
    guild=discord.Object(id=get_secret("DISCORD_GUILD_ID"))
)
@app_commands.choices(
    week_day=[
        app_commands.Choice(name="Segunda-Feira", value="segunda"),
        app_commands.Choice(name="Terça-Feira", value="terça"),
        app_commands.Choice(name="Quarta-Feira", value="quarta"),
        app_commands.Choice(name="Quinta-Feira", value="quinta"),
        app_commands.Choice(name="Sexta-Feira", value="sexta"),
    ]
)
@discord.app_commands.describe(
    week_day="Dia da semana para montar a planning do dia."
)
async def planning_daily(interaction: discord.Interaction, week_day: Optional[app_commands.Choice[str]] = None):
    if week_day is None:
        dia_value = weekday_default_ptbr_no_feira()
        dia_name = {
            "segunda": "Segunda-Feira",
            "terça": "Terça-Feira",
            "quarta": "Quarta-Feira",
            "quinta": "Quinta-Feira",
            "sexta": "Sexta-Feira"
        }[dia_value]
    else:
        dia_value = week_day.value
        dia_name = week_day.name

    await interaction.response.defer(ephemeral=True)
    await create_planning_daily(interaction, dia_value, dia_name)


# @client.event
# async def on_message(message):
#     global notified_today, notification_task
#     now = datetime.now()
#
#     # Checa se a mensagem é do usuário especificado, no canal e servidor especificado
#     if (
#             (message.guild is not None and message.guild.id == get_secret("DISCORD_GUILD_ID")) and
#             message.channel.id == get_secret("DISCORD_CHANNEL_ID") and
#             message.author.id == get_secret("DISCORD_USER_ID")
#     ):
#         if not notified_today or now.date() > notified_today:  # Primeiro envio do dia
#             notified_today = now.date()
#             user = await client.fetch_user(get_secret("DISCORD_USER_ID"))
#             notification_task = asyncio.create_task(send_notifications(user))
#             command = f'/home/ana_laura/AppImages/deckboard.appimage --no-sandbox %U'
#             # await execute_shell_command(command)
#         else:
#             await stop_notifications()  # Desliga as notificações se o usuário mandar outra mensagem
#
#     elif message.channel.id == get_secret("DM_ID") and message.author.id == get_secret("DISCORD_USER_ID"):
#         await stop_notifications()  # Desliga as notificações se o usuário mandar outra mensagem