import os
from datetime import datetime
from collections import defaultdict
from threading import Thread
from zoneinfo import ZoneInfo

from flask import Flask
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

# ====== Configurações ======
TIMEZONE = ZoneInfo("America/Bahia")       # Horário de Salvador/BA
HORA_INICIO = 7                            # início (7:00)
HORA_FIM = 11                              # fim    (11:00)
HORARIO_ATIVO = True                       # True = respeita janela / False = aceita sempre
MAX_PER_DAY = 10                           # máximo de perguntas no dia
ONE_PER_USER = True                        # True = 1 pergunta por usuário/dia

TOKEN = os.environ.get("TELEGRAM_TOKEN")   # defina no Render (NÃO hardcode!)
if not TOKEN:
    raise RuntimeError("Defina a env var TELEGRAM_TOKEN no Render.")

# Admin opcional: restrição do /listar (IDs numéricos separados por vírgula)
ADMIN_IDS = {int(x) for x in os.environ.get("ADMIN_IDS", "").split(",") if x.strip().isdigit()}

# ====== Armazenamento em memória (por dia) ======
perguntas_by_day = defaultdict(list)       # {date: [ {user_id,nome,texto,hora} , ... ]}
user_asked_by_day = defaultdict(set)       # {date: {user_id, ...}}

def hoje():
    return datetime.now(TIMEZONE).date()

def dentro_da_janela(agora: datetime) -> bool:
    dia_semana = agora.weekday()  # 0=seg, 6=dom
    return (0 <= dia_semana <= 4) and (HORA_INICIO <= agora.hour < HORA_FIM)

MENSAGEM_AVISO = (
    f"⏰ *Horário de funcionamento:*\n"
    f"• Segunda a sexta, das *{HORA_INICIO}:00* às *{HORA_FIM}:00* (horário de Salvador/BA).\n"
    f"• *Máximo de {MAX_PER_DAY}* perguntas por dia no grupo.\n"
    f"• *1 pergunta por pessoa* por dia."
)

# ====== Handlers ======
async def comando_pergunta(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.chat.type not in ("group", "supergroup"):
        await update.message.reply_text("Use /pergunta dentro do *grupo*.", parse_mode="Markdown")
        return

    texto = " ".join(context.args).strip()
    if not texto:
        await update.message.reply_text("❌ Escreva sua pergunta depois de /pergunta.")
        return

    agora = datetime.now(TIMEZONE)
    dia = hoje()
    user_id = update.message.from_user.id
    nome = update.message.from_user.first_name or "Aluno(a)"

    # Limites globais do dia
    if len(perguntas_by_day[dia]) >= MAX_PER_DAY:
        await update.message.reply_text("🚫 Limite diário de perguntas já foi atingido. Tente amanhã!")
        return

    # 1 por usuário/dia
    if ONE_PER_USER and user_id in user_asked_by_day[dia]:
        await update.message.reply_text("⚠️ Você já enviou 1 pergunta hoje. Aguarde até amanhã.")
        return

    # Janela de horário/dias
    if HORARIO_ATIVO and not dentro_da_janela(agora):
        await update.message.reply_text(MENSAGEM_AVISO, parse_mode="Markdown")
        return

    # Registrar
    perguntas_by_day[dia].append({
        "user_id": user_id,
        "nome": nome,
        "texto": texto,
        "hora": agora.strftime("%H:%M"),
    })
    user_asked_by_day[dia].add(user_id)
    await update.message.reply_text("✅ Pergunta registrada com sucesso!")

async def comando_listar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Só no privado e opcionalmente restrito a admins
    if update.message.chat.type != "private":
        await update.message.reply_text("Envie /listar no *privado*.", parse_mode="Markdown")
        return
    if ADMIN_IDS and update.message.from_user.id not in ADMIN_IDS:
        await update.message.reply_text("🚫 Você não tem permissão para listar.")
        return

    dia = hoje()
    itens = perguntas_by_day.get(dia, [])
    if not itens:
        await update.message.reply_text("Nenhuma pergunta registrada hoje.")
        return

    msg = ["📋 *Perguntas recebidas hoje:*\n"]
    for i, p in enumerate(itens, 1):
        msg.append(f"{i}. 👤 *{p['nome']}* ({p['hora']})\n   💬 {p['texto']}\n")
    await update.message.reply_text("\n".join(msg), parse_mode="Markdown")

async def comando_horario(update: Update, context: ContextTypes.DEFAULT_TYPE):
    estado = "ligado ✅" if HORARIO_ATIVO else "desligado ⚪"
    await update.message.reply_text(f"{MENSAGEM_AVISO}\n\nEstado da janela: *{estado}*", parse_mode="Markdown")

# ====== Bot + Flask juntos ======
flask_app = Flask(__name__)

@flask_app.get("/health")
def health():
    return "ok", 200

def run_bot():
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("pergunta", comando_pergunta))
    app.add_handler(CommandHandler("listar", comando_listar))
    app.add_handler(CommandHandler("horario", comando_horario))
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    # Inicia o bot em uma thread e o Flask como Web Service (Render exige porta aberta)
    Thread(target=run_bot, daemon=True).start()
    flask_app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "10000")))
