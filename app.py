<<<<<<< HEAD
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters
from datetime import datetime
import pytz
from flask import Flask
from threading import Thread

# ============================
# CONFIGURAÇÕES
# ============================
TOKEN = "7492540959:AAFatZvdk1gN2y5UD-AkQUJt_b6P5yqE-_4"

# Lista para armazenar perguntas no formato (nome, pergunta, hora)
perguntas = []

# Controle de usuários que já mandaram no dia
usuarios_hoje = {}

# Horário permitido (Brasília)
HORA_INICIO = 7  # 7:00
HORA_FIM = 22   # 22:00

# Ativar restrição de horário
HORARIO_ATIVO = False

# Fuso horário de Brasília
TZ_BR = pytz.timezone("America/Sao_Paulo")

# Lista de admins (sem @)
ADMINS_AUTORIZADOS = ["antoniomcpio"]

# Mensagens
MENSAGEM_AVISO = f"⏰ Perguntas só podem ser enviadas de segunda a sexta, das {HORA_INICIO}:00 às {HORA_FIM}:00 (horário de Brasília)"

MENSAGEM_BOAS_VINDAS = """👋 Olá! Eu sou o Bot Admin da **Comunidade Pio INBDE**.

🎯 **Como funciona:**
• Use o comando `/pergunta` seguido da sua dúvida
• Sua pergunta será enviada para o Prof. Antonio Pio
• Limite: 1 pergunta por pessoa por dia, máximo 10 perguntas/dia

📚 **Exemplo:**
`/pergunta Como calcular a resistência de um material?`
"""

# Variável temporária para resposta do admin
resposta_admin = {}

# ============================
# FUNÇÕES
# ============================

def is_admin(user):
    username = user.username
    if username:
        return username.lower() in [admin.lower() for admin in ADMINS_AUTORIZADOS]
    return False

# /start
async def start_comando(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.chat.type == "private":
        user = update.message.from_user
        if is_admin(user):
            await update.message.reply_text(
                f"👨‍🏫 Olá Professor {user.first_name}! Você tem acesso administrativo.\n\nUse `/listar` para ver as perguntas recebidas.",
                parse_mode="Markdown")
        else:
            await update.message.reply_text(MENSAGEM_BOAS_VINDAS,
                                            parse_mode="Markdown")

# /pergunta
async def nova_pergunta(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global perguntas, usuarios_hoje

    if update.message.chat.type in ["group", "supergroup"]:
        texto = " ".join(context.args)
        if not texto:
            await update.message.reply_text("❌ Por favor, escreva sua pergunta depois do comando /pergunta")
            return

        agora = datetime.now(TZ_BR)
        dia_semana = agora.weekday()
        hora_atual = agora.hour
        user_id = update.message.from_user.id
        nome = update.message.from_user.first_name

        # Reset diário
        data_hoje = agora.date()
        if usuarios_hoje.get("data") != data_hoje:
            usuarios_hoje = {"data": data_hoje}
            perguntas.clear()

        # Limite de 10 perguntas/dia
        if len(perguntas) >= 10:
            await update.message.reply_text("⚠️ O limite de 10 perguntas de hoje já foi atingido.")
            return

        # Limite 1 por usuário
        if user_id in usuarios_hoje:
            await update.message.reply_text("⚠️ Você já enviou uma pergunta hoje. Tente novamente amanhã.")
            return

        if HORARIO_ATIVO:
            if 0 <= dia_semana <= 4 and HORA_INICIO <= hora_atual < HORA_FIM:
                perguntas.append((nome, texto, agora.strftime("%H:%M")))
                usuarios_hoje[user_id] = True
                await update.message.reply_text("✅ Pergunta registrada com sucesso!")
            else:
                await update.message.reply_text(MENSAGEM_AVISO)
        else:
            perguntas.append((nome, texto, agora.strftime("%H:%M")))
            usuarios_hoje[user_id] = True
            await update.message.reply_text("✅ Pergunta registrada com sucesso! (horário ignorado)")

# /listar
async def listar_perguntas(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.chat.type == "private":
        user = update.message.from_user
        if not is_admin(user):
            await update.message.reply_text(MENSAGEM_BOAS_VINDAS,
                                            parse_mode="Markdown")
            return

        if perguntas:
            mensagem = "📋 *Perguntas recebidas hoje:*\n\n"
            for i, (nome, pergunta, hora) in enumerate(perguntas, 1):
                mensagem += f"{i}. 👤 *{nome}* ({hora})\n   💬 {pergunta}\n\n"
            mensagem += f"📊 Total: {len(perguntas)}/10 perguntas\n👥 Usuários: {len([k for k in usuarios_hoje.keys() if k != 'data'])}"
            await update.message.reply_text(mensagem, parse_mode="Markdown")
        else:
            await update.message.reply_text("📋 Nenhuma pergunta registrada hoje.\n📊 Status: 0/10 perguntas")

# /responder (admin)
async def iniciar_resposta(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global resposta_admin
    user = update.message.from_user
    if not is_admin(user):
        await update.message.reply_text("❌ Apenas admins podem usar este comando.")
        return

    if not perguntas:
        await update.message.reply_text("⚠️ Não há perguntas para responder.")
        return

    # Mostrar perguntas enumeradas
    mensagem = "📝 Escolha o número da pergunta que deseja responder:\n\n"
    for i, (nome, pergunta, hora) in enumerate(perguntas, 1):
        mensagem += f"{i}. 👤 {nome} ({hora})\n   💬 {pergunta}\n\n"
    resposta_admin[user.id] = {"etapa": "escolher", "respostas": [], "pergunta_selecionada": None}
    await update.message.reply_text(mensagem)

# Receber mensagens do admin para resposta
async def registrar_resposta(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global resposta_admin
    user = update.message.from_user
    if user.id in resposta_admin:
        estado = resposta_admin[user.id]
        texto = update.message.text

        if estado["etapa"] == "escolher":
            try:
                escolha = int(texto)
                if escolha < 1 or escolha > len(perguntas):
                    raise ValueError
                estado["pergunta_selecionada"] = escolha - 1
                estado["etapa"] = "respondendo"
                await update.message.reply_text("✏️ Ok! Agora envie a resposta. Quando terminar, use /fimresponder")
            except:
                await update.message.reply_text("❌ Número inválido. Digite novamente.")
        elif estado["etapa"] == "respondendo":
            estado["respostas"].append(update.message)

# /fimresponder
async def fim_responder(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global resposta_admin
    user = update.message.from_user
    if user.id not in resposta_admin or resposta_admin[user.id]["etapa"] != "respondendo":
        return

    estado = resposta_admin[user.id]
    index = estado["pergunta_selecionada"]
    pergunta = perguntas[index]
    mensagens = estado["respostas"]

    texto_final = f"📌 *Pergunta:* {pergunta[1]}\n\n*Resposta:*\n"
    for msg in mensagens:
        if msg.text:
            texto_final += msg.text + "\n"
        # Para imagens ou vídeos, você pode adaptar aqui

    # Limpar estado do admin
    del resposta_admin[user.id]

    await update.message.reply_text("✅ Resposta enviada com sucesso!")
    # Aqui você deveria encaminhar para o grupo (se houver chat_id fixo)

# ============================
# Mensagens privadas que não são comandos
# ============================
async def mensagem_privada(update: Update, context: ContextTypes.DEFAULT_TYPE):
    pass  # pode ignorar mensagens privadas normais

# ============================
# Servidor Flask (para UptimeRobot)
# ============================
app_flask = Flask(__name__)

@app_flask.route("/")
def home():
    return "🤖 Bot Telegram está rodando!"

def run_flask():
    app_flask.run(host="0.0.0.0", port=5000)

# ============================
# MAIN
# ============================
def main():
    Thread(target=run_flask, daemon=True).start()

    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start_comando))
    app.add_handler(CommandHandler("pergunta", nova_pergunta))
    app.add_handler(CommandHandler("listar", listar_perguntas))
    app.add_handler(CommandHandler("responder", iniciar_resposta))
    app.add_handler(CommandHandler("fimresponder", fim_responder))
    app.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, registrar_resposta))
    app.run_polling()

if __name__ == "__main__":
    main()
=======
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters
from datetime import datetime
import pytz
from flask import Flask
from threading import Thread

# ============================
# CONFIGURAÇÕES
# ============================
TOKEN = "7492540959:AAFatZvdk1gN2y5UD-AkQUJt_b6P5yqE-_4"

# Lista para armazenar perguntas no formato (nome, pergunta, hora)
perguntas = []

# Controle de usuários que já mandaram no dia
usuarios_hoje = {}

# Horário permitido (Brasília)
HORA_INICIO = 7  # 7:00
HORA_FIM = 22   # 22:00

# Ativar restrição de horário
HORARIO_ATIVO = False

# Fuso horário de Brasília
TZ_BR = pytz.timezone("America/Sao_Paulo")

# Lista de admins (sem @)
ADMINS_AUTORIZADOS = ["antoniomcpio"]

# Mensagens
MENSAGEM_AVISO = f"⏰ Perguntas só podem ser enviadas de segunda a sexta, das {HORA_INICIO}:00 às {HORA_FIM}:00 (horário de Brasília)"

MENSAGEM_BOAS_VINDAS = """👋 Olá! Eu sou o Bot Admin da **Comunidade Pio INBDE**.

🎯 **Como funciona:**
• Use o comando `/pergunta` seguido da sua dúvida
• Sua pergunta será enviada para o Prof. Antonio Pio
• Limite: 1 pergunta por pessoa por dia, máximo 10 perguntas/dia

📚 **Exemplo:**
`/pergunta Como calcular a resistência de um material?`
"""

# Variável temporária para resposta do admin
resposta_admin = {}

# ============================
# FUNÇÕES
# ============================

def is_admin(user):
    username = user.username
    if username:
        return username.lower() in [admin.lower() for admin in ADMINS_AUTORIZADOS]
    return False

# /start
async def start_comando(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.chat.type == "private":
        user = update.message.from_user
        if is_admin(user):
            await update.message.reply_text(
                f"👨‍🏫 Olá Professor {user.first_name}! Você tem acesso administrativo.\n\nUse `/listar` para ver as perguntas recebidas.",
                parse_mode="Markdown")
        else:
            await update.message.reply_text(MENSAGEM_BOAS_VINDAS,
                                            parse_mode="Markdown")

# /pergunta
async def nova_pergunta(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global perguntas, usuarios_hoje

    if update.message.chat.type in ["group", "supergroup"]:
        texto = " ".join(context.args)
        if not texto:
            await update.message.reply_text("❌ Por favor, escreva sua pergunta depois do comando /pergunta")
            return

        agora = datetime.now(TZ_BR)
        dia_semana = agora.weekday()
        hora_atual = agora.hour
        user_id = update.message.from_user.id
        nome = update.message.from_user.first_name

        # Reset diário
        data_hoje = agora.date()
        if usuarios_hoje.get("data") != data_hoje:
            usuarios_hoje = {"data": data_hoje}
            perguntas.clear()

        # Limite de 10 perguntas/dia
        if len(perguntas) >= 10:
            await update.message.reply_text("⚠️ O limite de 10 perguntas de hoje já foi atingido.")
            return

        # Limite 1 por usuário
        if user_id in usuarios_hoje:
            await update.message.reply_text("⚠️ Você já enviou uma pergunta hoje. Tente novamente amanhã.")
            return

        if HORARIO_ATIVO:
            if 0 <= dia_semana <= 4 and HORA_INICIO <= hora_atual < HORA_FIM:
                perguntas.append((nome, texto, agora.strftime("%H:%M")))
                usuarios_hoje[user_id] = True
                await update.message.reply_text("✅ Pergunta registrada com sucesso!")
            else:
                await update.message.reply_text(MENSAGEM_AVISO)
        else:
            perguntas.append((nome, texto, agora.strftime("%H:%M")))
            usuarios_hoje[user_id] = True
            await update.message.reply_text("✅ Pergunta registrada com sucesso! (horário ignorado)")

# /listar
async def listar_perguntas(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.chat.type == "private":
        user = update.message.from_user
        if not is_admin(user):
            await update.message.reply_text(MENSAGEM_BOAS_VINDAS,
                                            parse_mode="Markdown")
            return

        if perguntas:
            mensagem = "📋 *Perguntas recebidas hoje:*\n\n"
            for i, (nome, pergunta, hora) in enumerate(perguntas, 1):
                mensagem += f"{i}. 👤 *{nome}* ({hora})\n   💬 {pergunta}\n\n"
            mensagem += f"📊 Total: {len(perguntas)}/10 perguntas\n👥 Usuários: {len([k for k in usuarios_hoje.keys() if k != 'data'])}"
            await update.message.reply_text(mensagem, parse_mode="Markdown")
        else:
            await update.message.reply_text("📋 Nenhuma pergunta registrada hoje.\n📊 Status: 0/10 perguntas")

# /responder (admin)
async def iniciar_resposta(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global resposta_admin
    user = update.message.from_user
    if not is_admin(user):
        await update.message.reply_text("❌ Apenas admins podem usar este comando.")
        return

    if not perguntas:
        await update.message.reply_text("⚠️ Não há perguntas para responder.")
        return

    # Mostrar perguntas enumeradas
    mensagem = "📝 Escolha o número da pergunta que deseja responder:\n\n"
    for i, (nome, pergunta, hora) in enumerate(perguntas, 1):
        mensagem += f"{i}. 👤 {nome} ({hora})\n   💬 {pergunta}\n\n"
    resposta_admin[user.id] = {"etapa": "escolher", "respostas": [], "pergunta_selecionada": None}
    await update.message.reply_text(mensagem)

# Receber mensagens do admin para resposta
async def registrar_resposta(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global resposta_admin
    user = update.message.from_user
    if user.id in resposta_admin:
        estado = resposta_admin[user.id]
        texto = update.message.text

        if estado["etapa"] == "escolher":
            try:
                escolha = int(texto)
                if escolha < 1 or escolha > len(perguntas):
                    raise ValueError
                estado["pergunta_selecionada"] = escolha - 1
                estado["etapa"] = "respondendo"
                await update.message.reply_text("✏️ Ok! Agora envie a resposta. Quando terminar, use /fimresponder")
            except:
                await update.message.reply_text("❌ Número inválido. Digite novamente.")
        elif estado["etapa"] == "respondendo":
            estado["respostas"].append(update.message)

# /fimresponder
async def fim_responder(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global resposta_admin
    user = update.message.from_user
    if user.id not in resposta_admin or resposta_admin[user.id]["etapa"] != "respondendo":
        return

    estado = resposta_admin[user.id]
    index = estado["pergunta_selecionada"]
    pergunta = perguntas[index]
    mensagens = estado["respostas"]

    texto_final = f"📌 *Pergunta:* {pergunta[1]}\n\n*Resposta:*\n"
    for msg in mensagens:
        if msg.text:
            texto_final += msg.text + "\n"
        # Para imagens ou vídeos, você pode adaptar aqui

    # Limpar estado do admin
    del resposta_admin[user.id]

    await update.message.reply_text("✅ Resposta enviada com sucesso!")
    # Aqui você deveria encaminhar para o grupo (se houver chat_id fixo)

# ============================
# Mensagens privadas que não são comandos
# ============================
async def mensagem_privada(update: Update, context: ContextTypes.DEFAULT_TYPE):
    pass  # pode ignorar mensagens privadas normais

# ============================
# Servidor Flask (para UptimeRobot)
# ============================
app_flask = Flask(__name__)

@app_flask.route("/")
def home():
    return "🤖 Bot Telegram está rodando!"

def run_flask():
    app_flask.run(host="0.0.0.0", port=5000)

# ============================
# MAIN
# ============================
def main():
    Thread(target=run_flask, daemon=True).start()

    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start_comando))
    app.add_handler(CommandHandler("pergunta", nova_pergunta))
    app.add_handler(CommandHandler("listar", listar_perguntas))
    app.add_handler(CommandHandler("responder", iniciar_resposta))
    app.add_handler(CommandHandler("fimresponder", fim_responder))
    app.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, registrar_resposta))
    app.run_polling()

if __name__ == "__main__":
    main()
>>>>>>> 2c5936f684e6cc59f34b08edbc5707a28e0a1d7a
