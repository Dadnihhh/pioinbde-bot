from telegram import Update, InputMediaPhoto, InputMediaVideo
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters, ConversationHandler
from datetime import datetime
import pytz
from flask import Flask
from threading import Thread
import os

# Token do Telegram e ID do grupo
TOKEN = "7492540959:AAFatZvdk1gN2y5UD-AkQUJt_b6P5yqE-_4"
CHAT_ID_GRUPO = -1001234567890  # Substitua pelo seu ID de grupo real

# Lista de perguntas do dia
perguntas = []

# Controle de usuários que já mandaram pergunta hoje
usuarios_hoje = {}

# Horário permitido (Brasília)
HORA_INICIO = 7
HORA_FIM = 22
HORARIO_ATIVO = False
TZ_BR = pytz.timezone("America/Sao_Paulo")

# Lista de admins autorizados
ADMINS_AUTORIZADOS = ["antoniomcpio"]  # sem @

# Mensagens
MENSAGEM_AVISO = f"⏰ Perguntas só podem ser enviadas de segunda a sexta, das {HORA_INICIO}:00 às {HORA_FIM}:00 (horário de Brasília)"
MENSAGEM_BOAS_VINDAS = """👋 Olá! Eu sou o Bot Admin da **Comunidade Pio INBDE**.

🎯 **Como funciona:**
• Use o comando `/pergunta` seguido da sua dúvida
• Sua pergunta será enviada para o Prof. Antonio Pio no grupo da comunidade
• Horário: Segunda a sexta, das 7h às 22h (Brasília)
• Limite: 1 pergunta por pessoa por dia

📚 **Exemplo:**
`/pergunta Como calcular a resistência de um material?`

✅ Sua pergunta chegará ao professor e será respondida no grupo oficial!"""

# ============================
# Funções auxiliares
# ============================
def is_admin(user):
    username = user.username
    return username and username.lower() in [admin.lower() for admin in ADMINS_AUTORIZADOS]

def reset_dia():
    global usuarios_hoje, perguntas
    agora = datetime.now(TZ_BR)
    if usuarios_hoje.get("data") != agora.date():
        usuarios_hoje = {"data": agora.date()}
        perguntas.clear()

# ============================
# Comando /pergunta
# ============================
async def nova_pergunta(update: Update, context: ContextTypes.DEFAULT_TYPE):
    reset_dia()
    if update.message.chat.type not in ["group", "supergroup"]:
        return

    texto = " ".join(context.args)
    if not texto:
        await update.message.reply_text("❌ Por favor, escreva sua pergunta depois do comando /pergunta")
        return

    agora = datetime.now(TZ_BR)
    user_id = update.message.from_user.id
    nome = update.message.from_user.first_name

    if len(perguntas) >= 10:
        await update.message.reply_text("⚠️ O limite de 10 perguntas de hoje já foi atingido.")
        return

    if user_id in usuarios_hoje:
        await update.message.reply_text("⚠️ Você já enviou uma pergunta hoje. Tente novamente amanhã.")
        return

    hora_atual = agora.hour
    dia_semana = agora.weekday()

    if HORARIO_ATIVO:
        if not (0 <= dia_semana <= 4 and HORA_INICIO <= hora_atual < HORA_FIM):
            await update.message.reply_text(MENSAGEM_AVISO)
            return

    perguntas.append((nome, texto, agora.strftime("%H:%M")))
    usuarios_hoje[user_id] = True
    await update.message.reply_text("✅ Pergunta registrada com sucesso!\n\n📩 Sua pergunta foi enviada para o Prof. Antonio Pio na Comunidade Pio INBDE.")

# ============================
# Comando /start
# ============================
async def start_comando(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.chat.type != "private":
        return

    user = update.message.from_user
    if is_admin(user):
        await update.message.reply_text(f"👨‍🏫 Olá Professor {user.first_name}! Você tem acesso administrativo.\n\nUse `/listar` para ver as perguntas recebidas.", parse_mode="Markdown")
    else:
        await update.message.reply_text(MENSAGEM_BOAS_VINDAS, parse_mode="Markdown")

# ============================
# Comando /listar (admins)
# ============================
async def listar_perguntas(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.chat.type != "private":
        return
    user = update.message.from_user
    if not is_admin(user):
        await update.message.reply_text(MENSAGEM_BOAS_VINDAS, parse_mode="Markdown")
        return

    reset_dia()

    if perguntas:
        mensagem = "📋 *Perguntas recebidas hoje:*\n\n"
        for i, (nome, pergunta, hora) in enumerate(perguntas, 1):
            mensagem += f"{i}. 👤 *{nome}* ({hora})\n   💬 {pergunta}\n\n"
        mensagem += f"\n📊 Total: {len(perguntas)}/10 perguntas\n👥 Usuários: {len([k for k in usuarios_hoje.keys() if k != 'data'])}"
        await update.message.reply_text(mensagem, parse_mode="Markdown")
    else:
        await update.message.reply_text("📋 Nenhuma pergunta registrada hoje.\n📊 Status: 0/10 perguntas")

# ============================
# Comando /responder (apenas admins)
# ============================
SELECIONAR, RESPOSTA = range(2)
resposta_atual = {}

async def responder_inicio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    if not is_admin(user):
        await update.message.reply_text("❌ Apenas admins podem usar este comando.")
        return ConversationHandler.END

    reset_dia()
    if not perguntas:
        await update.message.reply_text("⚠️ Não há perguntas para responder hoje.")
        return ConversationHandler.END

    mensagem = "📝 Selecione o número da pergunta que deseja responder:\n\n"
    for i, (nome, pergunta, hora) in enumerate(perguntas, 1):
        mensagem += f"{i}. 👤 {nome} ({hora}) - {pergunta}\n"
    await update.message.reply_text(mensagem)
    return SELECIONAR

async def selecionar_pergunta(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        indice = int(update.message.text) - 1
        if not (0 <= indice < len(perguntas)):
            raise ValueError
    except ValueError:
        await update.message.reply_text("❌ Número inválido. Tente novamente.")
        return SELECIONAR

    context.user_data["responder_indice"] = indice
    context.user_data["resposta_msgs"] = []
    await update.message.reply_text("✅ Pergunta selecionada. Agora envie a resposta (texto, imagens ou vídeos). Quando terminar, use /fimresponder")
    return RESPOSTA

async def registrar_resposta(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["resposta_msgs"].append(update.message)
    return RESPOSTA

async def fim_responder(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    if not is_admin(user):
        return ConversationHandler.END

    indice = context.user_data.get("responder_indice")
    if indice is None:
        await update.message.reply_text("❌ Nenhuma pergunta selecionada.")
        return ConversationHandler.END

    pergunta_info = perguntas[indice]
    mensagem_final = f"📌 *Pergunta:* {pergunta_info[1]}\n👤 Pergunta por: {pergunta_info[0]} ({pergunta_info[2]})\n\n*Resposta:*"

    mensagens = context.user_data.get("resposta_msgs", [])
    texto_resposta = ""
    media = []
    for msg in mensagens:
        if msg.text:
            texto_resposta += f"{msg.text}\n"
        if msg.photo:
            media.append(InputMediaPhoto(msg.photo[-1].file_id))
        if msg.video:
            media.append(InputMediaVideo(msg.video.file_id))

    app = context.application
    if media:
        await app.bot.send_message(chat_id=CHAT_ID_GRUPO, text=mensagem_final + "\n" + texto_resposta)
        await app.bot.send_media_group(chat_id=CHAT_ID_GRUPO, media=media)
    else:
        await app.bot.send_message(chat_id=CHAT_ID_GRUPO, text=mensagem_final + "\n" + texto_resposta)

    await update.message.reply_text("✅ Resposta enviada com sucesso!")
    return ConversationHandler.END

# ============================
# Flask para uptime
# ============================
app_flask = Flask(__name__)

@app_flask.route("/")
def home():
    return "🤖 Bot Telegram está rodando!"

def run_flask():
    app_flask.run(host="0.0.0.0", port=5000)

# ============================
# Função principal
# ============================
def main():
    Thread(target=run_flask, daemon=True).start()

    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start_comando))
    app.add_handler(CommandHandler("pergunta", nova_pergunta))
    app.add_handler(CommandHandler("listar", listar_perguntas))

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("responder", responder_inicio)],
        states={
            SELECIONAR: [MessageHandler(filters.TEXT & ~filters.COMMAND, selecionar_pergunta)],
            RESPOSTA: [MessageHandler(filters.ALL & ~filters.COMMAND, registrar_resposta)],
        },
        fallbacks=[CommandHandler("fimresponder", fim_responder)],
    )
    app.add_handler(conv_handler)

    app.run_polling()

if __name__ == "__main__":
    main()
