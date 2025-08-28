import os
from datetime import datetime
from threading import Thread

import pytz
from dotenv import load_dotenv
from flask import Flask
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

# ============================
# Carregar variáveis de ambiente
# ============================
load_dotenv()
TOKEN = os.getenv("TELEGRAM_TOKEN") or "7492540959:AAFatZvdk1gN2y5UD-AkQUJt_b6P5yqE-_4"

# ============================
# Configurações do Bot
# ============================
# Lista de perguntas no formato (nome, pergunta, hora)
perguntas = []

# Usuários que já enviaram pergunta hoje
usuarios_hoje = {}

# Horário permitido (Brasília)
HORA_INICIO = 7
HORA_FIM = 22
HORARIO_ATIVO = False

# Fuso horário de Brasília
TZ_BR = pytz.timezone("America/Sao_Paulo")

# Lista de admins (sem @)
ADMINS_AUTORIZADOS = ["antoniomcpio"]

# Mensagens
MENSAGEM_AVISO = f"⏰ Perguntas só podem ser enviadas de segunda a sexta, das {HORA_INICIO}:00 às {HORA_FIM}:00 (horário de Brasília)"
MENSAGEM_BOAS_VINDAS = f"""👋 Olá! Eu sou o Bot Admin da **Comunidade Pio INBDE**.

🎯 **Como funciona:**
• Use o comando `/pergunta` seguido da sua dúvida (apenas no privado)
• Sua pergunta será enviada para o Prof. Antonio Pio no grupo da comunidade
• Horário: Segunda a sexta, das 7h às 22h (Brasília)
• Limite: 1 pergunta por pessoa por dia

📚 **Exemplo:**
`/pergunta Como calcular a resistência de um material?`

✅ Sua pergunta chegará ao professor e será respondida no grupo oficial!
"""

# ============================
# Funções auxiliares
# ============================
def is_admin(user) -> bool:
    username = user.username
    return username and username.lower() in [adm.lower() for adm in ADMINS_AUTORIZADOS]

def reset_diario():
    agora = datetime.now(TZ_BR).date()
    if usuarios_hoje.get("data") != agora:
        usuarios_hoje.clear()
        usuarios_hoje["data"] = agora
        perguntas.clear()

# ============================
# Comando /pergunta
# ============================
async def nova_pergunta(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.chat.type != "private":
        await update.message.reply_text("❌ Por favor, use o comando /pergunta apenas no privado do bot.")
        return

    reset_diario()
    user_id = update.message.from_user.id
    nome = update.message.from_user.first_name
    texto = " ".join(context.args)

    if not texto:
        await update.message.reply_text("❌ Por favor, escreva sua pergunta depois do comando /pergunta")
        return

    if user_id in usuarios_hoje:
        await update.message.reply_text("⚠️ Você já enviou uma pergunta hoje. Tente novamente amanhã.")
        return

    agora = datetime.now(TZ_BR)
    dia_semana = agora.weekday()
    hora_atual = agora.hour

    if HORARIO_ATIVO:
        if 0 <= dia_semana <= 4 and HORA_INICIO <= hora_atual < HORA_FIM:
            perguntas.append((nome, texto, agora.strftime("%H:%M")))
            usuarios_hoje[user_id] = True
            await update.message.reply_text("✅ Pergunta registrada com sucesso!\n📩 Sua pergunta foi enviada para o Prof. Antonio Pio.")
        else:
            await update.message.reply_text(MENSAGEM_AVISO)
    else:
        perguntas.append((nome, texto, agora.strftime("%H:%M")))
        usuarios_hoje[user_id] = True
        await update.message.reply_text("✅ Pergunta registrada com sucesso! (horário ignorado)")

# ============================
# Comando /start
# ============================
async def start_comando(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.chat.type != "private":
        return
    user = update.message.from_user
    if is_admin(user):
        await update.message.reply_text(
            f"👨‍🏫 Olá Professor {user.first_name}! Você tem acesso administrativo.\n\nUse `/listar` para ver as perguntas recebidas.",
            parse_mode="Markdown",
        )
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

    if perguntas:
        mensagem_formatada = "📋 *Perguntas recebidas hoje:*\n\n"
        for i, (nome, pergunta, hora) in enumerate(perguntas, 1):
            mensagem_formatada += f"{i}. 👤 *{nome}* ({hora})\n   💬 {pergunta}\n\n"
        mensagem_formatada += f"📊 Total: {len(perguntas)}/10 perguntas\n👥 Usuários: {len([k for k in usuarios_hoje.keys() if k != 'data'])}"
        await update.message.reply_text(mensagem_formatada, parse_mode="Markdown")
    else:
        await update.message.reply_text("📋 Nenhuma pergunta registrada hoje.\n📊 Status: 0/10 perguntas")

# ============================
# Mensagem privada
# ============================
async def mensagem_privada(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.chat.type == "private":
        user = update.message.from_user
        if not is_admin(user):
            await update.message.reply_text(MENSAGEM_BOAS_VINDAS, parse_mode="Markdown")

# ============================
# Flask (para uptime)
# ============================
app_flask = Flask(__name__)

@app_flask.route("/")
def home():
    return "🤖 Bot Telegram está rodando!"

@app_flask.route("/status")
def status():
    return {
        "bot_ativo": True,
        "perguntas_hoje": len(perguntas),
        "usuarios_hoje": len([k for k in usuarios_hoje.keys() if k != "data"]),
        "horario_ativo": HORARIO_ATIVO
    }

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
    app.add_handler(MessageHandler(filters.ChatType.PRIVATE & ~filters.COMMAND, mensagem_privada))
    app.run_polling()

if __name__ == "__main__":
    main()
