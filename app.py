from flask import Flask, request, jsonify
from playwright.sync_api import sync_playwright
import json
import time
from threading import Lock

app = Flask(_name_)
browser_lock = Lock()  # Para evitar problemas com threads

def scrape_verdemar(ean):
    url_busca = f"https://www.loja.verdemaratevoce.com.br/busca?termo={ean}"
    result = {
        "ean": ean,
        "url_foto": None,
        "titulo": None,
        "descricao": None,
        "preco": None,
        "url_produto": None,
        "disponibilidade": None,
        "sucesso": False,
        "mensagem": None
    }
    
    with browser_lock:  # Garante que apenas uma thread use o Playwright por vez
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                viewport={"width": 1280, "height": 800},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/90.0.4430.212 Safari/537.36"
            )
            page = context.new_page()
            
            try:
                # 1. Acessa a página de busca
                page.goto(url_busca, timeout=60000)
                time.sleep(2)
                
                # 2. Espera e clica no primeiro produto
                page.wait_for_selector(".vip-card-produto", state="attached", timeout=15000)
                primeiro_produto = page.locator(".vip-card-produto").first
                primeiro_produto.scroll_into_view_if_needed()
                
                with page.expect_navigation(timeout=15000):
                    primeiro_produto.click()
                
                # 3. Salva a URL do produto
                result["url_produto"] = page.url
                result["sucesso"] = True
                
                # 4. Extrai a imagem do produto
                try:
                    img_element = page.locator("vip-image img").first
                    result["url_foto"] = img_element.get_attribute("src")
                except Exception as e:
                    result["mensagem"] = f"Erro ao extrair imagem: {str(e)}"
                
                # 5. Extrai o título
                try:
                    titulo_element = page.locator("div.text-lg.font-normal").first
                    result["titulo"] = titulo_element.text_content().strip()
                except Exception as e:
                    result["mensagem"] = f"Erro ao extrair título: {str(e)}"
                
                # 6. Extrai a descrição
                try:
                    descricao_element = page.locator("[data-cy='info-produto']").first
                    result["descricao"] = descricao_element.text_content().strip()
                except Exception as e:
                    result["mensagem"] = f"Erro ao extrair descrição: {str(e)}"
                
                # 7. Extrai o preço
                try:
                    preco_element = page.locator("span[data-cy='preco'].grande.font-bold").first
                    result["preco"] = preco_element.text_content().replace("R$&nbsp;", "R$ ").strip()
                except Exception as e:
                    result["mensagem"] = f"Erro ao extrair preço: {str(e)}"
                
                # 8. Verifica disponibilidade
                try:
                    disponivel = page.locator("text=Indisponível").count() == 0
                    result["disponibilidade"] = "Disponível" if disponivel else "Indisponível"
                except:
                    result["disponibilidade"] = "Informação não disponível"
                
            except Exception as e:
                result["mensagem"] = f"Erro geral: {str(e)}"
                page.screenshot(path=f"erro_verdemar_{ean}.png")
            finally:
                context.close()
                browser.close()
    
    return result

@app.route('/api/produto', methods=['GET'])
def get_produto():
    ean = request.args.get('ean')
    
    if not ean:
        return jsonify({
            "sucesso": False,
            "mensagem": "Parâmetro 'ean' é obrigatório"
        }), 400
    
    try:
        dados_produto = scrape_verdemar(ean)
        status_code = 200 if dados_produto["sucesso"] else 404
        return jsonify(dados_produto), status_code
    except Exception as e:
        return jsonify({
            "sucesso": False,
            "mensagem": f"Erro interno: {str(e)}",
            "ean": ean
        }), 500

@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({
        "status": "online",
        "versao": "1.0"
    })

if _name_ == '_main_':
    app.run(host='0.0.0.0', port=5000, threaded=True)
