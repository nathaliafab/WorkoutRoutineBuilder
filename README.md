# 🏋️‍♂️ **Workout Routine Builder**

Este script Python gera um cronograma semanal personalizado de vídeos do YouTube para suas rotinas de treino. O cronograma é salvo em um arquivo PDF que inclui vídeos recomendados para cada dia da semana, com miniaturas, títulos e links, e cada etapa é registrada em um arquivo de log.

## 📋 **Requisitos**

1. **Python**: Verifique se o Python está instalado em seu sistema.
2. **Dependências**: Instale as bibliotecas necessárias executando o comando:

   ```bash
   pip install -r requirements.txt
   ```

## ⚙️ **Configuração**

### 1. Criar o Arquivo `.env`

Na raiz do projeto, crie um arquivo chamado `.env` e adicione sua chave da API do YouTube. O conteúdo do arquivo deve ser:

   ```
   YOUTUBE_API_KEY=YOUR_YOUTUBE_API_KEY
   ```

   Substitua `YOUR_YOUTUBE_API_KEY` pela sua chave da API do YouTube, que pode ser obtida no [Google Cloud Console](https://console.cloud.google.com/).

### 2. Configurar o Arquivo `input_data.json`

Personalize o arquivo `input_data.json` de acordo com suas preferências. Aqui estão as chaves e suas descrições:

- **`youtube_channels`**: Lista de canais do YouTube a serem considerados.
  - `channel_id`: ID do canal.
  - `channel_name`: Nome do canal.
  - `include`: Indica se o canal deve ser incluído.
- **`rest_days`**: Dias da semana em que não haverá exercícios.
- **`exercise_categories`**: Categorias de exercícios a serem consideradas.
  - `category_name`: Nome da categoria.
  - `keywords`: Vídeos com títulos contendo essas palavras-chave serão considerados.
  - `include`: Indica se a categoria deve ser incluída.
  - `daily`: Indica se a categoria deve ser considerada diariamente.
- **`excluded_keywords`**: Vídeos com títulos contendo essas palavras-chave serão descartados.
- **`daily_video_schedule`**: Configurações do cronograma diário.
  - `min_duration_minutes`: Duração mínima dos vídeos em minutos.
  - `max_duration_minutes`: Duração máxima dos vídeos em minutos.
  - `min_videos_per_day`: Quantidade mínima de vídeos por dia.
  - `max_videos_per_day`: Quantidade máxima de vídeos por dia.
- **`additional_settings`**: Configurações adicionais.
  - `show_duration`: Exibir a duração total dos vídeos.
  - `show_thumbnail`: Exibir a miniatura dos vídeos.

Um exemplo já é fornecido no repositório, mas você pode alterá-lo conforme desejar.

### 3. Executar o Script

Para rodar o script, use o comando:

   ```bash
   python main.py
   ```

Certifique-se de que o arquivo `input_data.json` e o arquivo `.env` estejam na mesma pasta que o script `main.py`. O progresso do processo será registrado no arquivo de log, e o arquivo PDF gerado estará disponível ao final da execução.

## 🤝 **Contribuição**

Se você encontrar problemas ou tiver sugestões de melhorias, sinta-se à vontade para abrir uma issue ou enviar um pull request.
