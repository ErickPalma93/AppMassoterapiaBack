from flask import Blueprint, jsonify, request
import requests
import os

whatsapp_bp = Blueprint('whatsapp', __name__)

@whatsapp_bp.route('/send-confirmation', methods=['POST'])
def send_whatsapp_confirmation():
    """Envia confirmação de agendamento via WhatsApp"""
    try:
        data = request.get_json()
        
        # Dados do agendamento
        customer_name = data['customer']['name']
        customer_phone = data['customer']['phone']
        service_name = data['service']['name']
        service_price = data['service']['price']
        booking_date = data['booking_date']
        booking_time = data['booking_time']
        
        # Formatar a mensagem
        message = f"""Agendamento confirmado ✅

Data: {booking_date}
Horário: {booking_time}
Procedimento: {service_name}
Valor da sessão: R$ {service_price:.2f}

Endereço: João Luiz Tozzi 198a
Votorantim Park 1

Informamos que aceitamos atrasos de até 10 minutos após o horário agendado. Caso ultrapasse esse prazo, entrar em contato conosco."""

        # Se o serviço incluir sauna, adicionar observação
        if 'sauna' in service_name.lower():
            message += "\n\nPara sessão de sauna, trazer duas toalhas de banho."
        
        # Aqui você integraria com a API do WhatsApp
        # Por enquanto, vamos simular o envio
        
        # Exemplo de integração com WhatsApp Business API:
        # whatsapp_api_url = "https://graph.facebook.com/v17.0/YOUR_PHONE_NUMBER_ID/messages"
        # headers = {
        #     "Authorization": f"Bearer {os.getenv('WHATSAPP_ACCESS_TOKEN')}",
        #     "Content-Type": "application/json"
        # }
        # 
        # payload = {
        #     "messaging_product": "whatsapp",
        #     "to": customer_phone,
        #     "type": "text",
        #     "text": {"body": message}
        # }
        # 
        # response = requests.post(whatsapp_api_url, headers=headers, json=payload)
        
        # Por enquanto, retornamos sucesso simulado
        return jsonify({
            'success': True,
            'message': 'Confirmação enviada via WhatsApp',
            'whatsapp_message': message
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@whatsapp_bp.route('/webhook', methods=['GET', 'POST'])
def whatsapp_webhook():
    """Webhook para receber mensagens do WhatsApp"""
    if request.method == 'GET':
        # Verificação do webhook
        verify_token = request.args.get('hub.verify_token')
        challenge = request.args.get('hub.challenge')
        
        # Verificar se o token está correto
        if verify_token == os.getenv('WHATSAPP_VERIFY_TOKEN', 'massoterapia_evelin_webhook'):
            return challenge
        else:
            return 'Forbidden', 403
    
    elif request.method == 'POST':
        # Processar mensagens recebidas
        data = request.get_json()
        
        # Aqui você processaria as mensagens recebidas
        # Por exemplo, responder a perguntas sobre horários, cancelamentos, etc.
        
        return jsonify({'status': 'received'})
    
    return jsonify({'error': 'Method not allowed'}), 405

