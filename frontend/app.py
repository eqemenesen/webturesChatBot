from flask import Flask, request, render_template, session, jsonify
import pandas as pd
import json
from openai import OpenAI
import os
from datetime import timedelta
from dotenv import load_dotenv
import logging
import random
import string

load_dotenv()

df = pd.read_excel('caseStudy.xlsx')
df_structure = df.head().to_string()  


app = Flask(__name__)
app.logger.setLevel(logging.INFO)
app.logger.info(df_structure)

app.secret_key = os.urandom(24)
app.config['SESSION_PERMANENT'] = True
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(minutes=5)
# Generate a random string for the session cookie name
app.config['SESSION_COOKIE_NAME'] = 'flask_session_' + ''.join(random.choices(string.ascii_letters + string.digits, k=8))


client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

main_prompt = f"""Sen bir şirket asistanısın. Çalışanlar sana sorular sorabilir. Bu sorular genel ya da bağlı olduğun df hakkında olabilir. Bağlı olduğun df şirketin web sitesinin o aykı trafiğini içeriyor. df'in yapısı:

{df_structure}

soru sorulduğunu df hakkında mı yoksa genel bir soru mu olduğunu ayırt etmen gerekiyor. df hakkında örnek sorular: "Şubat ayında ne kadar trafik aldık?", "Şubat ayında Türkiye ve Mobilden gelen trafik sayısı kaçtır?", "Ocak ve Şubat ayında kaç tane whatsapp dönüşümü elde ettik?" tarzında. Cevaplarını her zaman aşağıdaki gibi, süslü parantezler içinde, json formatında vericeksin.

{{
    df_query : "",
    gpt_response: ""
}}

Eğer soru df hakkında ise df'te ilgili sonucu getirecek formatı df_query kısmına yazman gerekiyor ve gpt_response kısmını da df_query'den gelen cevabın sonuna eklenebileceği şekilde vermelisin. Örneğin:

"Şubat ayında aldığımız trafik " ya da "Şubat ayında Türkiye ve mobilde gelen trafik " gibi. Vereceğin gpt_response içindeki cevaplar df query den gelen sonuçla birleşecek. Cevaplarını veriken gelen sorgunun eklenebileceği bigi ver ve X kadardır gibi bir cümle kullanma 

Eğer sorulan soru df ile ilgili değilse cevabını aynı formatta df_query kısmını yukarıdaki gibi boş bırakarak vericeksin. vereceğin bütün cevaplar tam olarak bu json formatında olmak zorunda.
"""

app.logger.info(main_prompt)

@app.route('/reset_session', methods=['POST'])
def reset_session():
    session.clear()  # This clears the session
    return jsonify({"status": "success"}), 200

    
@app.route('/', methods=['GET', 'POST'])
def home():
    if request.method == 'POST':
        user_request = request.form['sorgu']
        
        # Make the API call
        response = client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role":"assistant", "content": main_prompt},
                {"role": "user", "content": user_request}
            ]
        )
        
        # Get the response text, assuming it's JSON-formatted
        gpt_text_response = response.choices[0].message.content.strip()
        
        try:
            response_data = json.loads(gpt_text_response)
            df_query = response_data.get('df_query', '')
            gpt_response = response_data.get('gpt_response', '')
        except json.JSONDecodeError as e:
            app.logger.error(f"Failed to decode JSON from GPT response: {e}")
            df_query = ''
            gpt_response = 'An error occurred while processing the response.'

        # If df_query is not empty, execute it against the DataFrame
        if df_query:
            try:
                # Evaluate the query safely. This is a basic example; you should look for safer alternatives.
                query_result = eval(df_query, {'df': df, '__builtins__': None}, {})
                # Append the result to the gpt_response
                final_response = f"{gpt_response} {query_result}"
            except Exception as e:
                app.logger.error(f"Error executing df_query: {e}")
                final_response = "Sorry, there was an error processing your request."
        else:
            # If df_query is empty, just use the gpt_response
            final_response = gpt_response
        
        app.logger.info(f"gpt_response--> {gpt_response}")
        app.logger.info(f"df_query--> {df_query}")
        
        if 'gpt_answers' not in session:
            session['gpt_answers'] = []
        session['gpt_answers'].append({'sorgu': user_request, 'cevap': final_response})
        session.modified = True

    else:
        if 'gpt_answers' not in session:
            session['gpt_answers'] = []

    return render_template('index.html', gpt_answers=session['gpt_answers'])

if __name__ == '__main__':
    app.run(debug=True)

