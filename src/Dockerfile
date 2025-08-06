# Usa uma imagem base oficial do Python para o seu projeto
FROM python:3.9-slim

# Define o diretório de trabalho dentro do contêiner
WORKDIR /app

# Copia o arquivo requirements.txt para o contêiner
COPY requirements.txt .

# Instala todas as dependências do Python
RUN pip install --no-cache-dir -r requirements.txt

# Copia o restante do código da sua aplicação para o contêiner
COPY . .

# Expõe a porta que a aplicação vai usar
EXPOSE 5000

# Comando para iniciar o servidor Flask
# Certifique-se de que 'app.py' é o nome do seu arquivo principal da aplicação
CMD ["flask", "run", "--host=0.0.0.0", "--port=5000"]