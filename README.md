# PDF Signer

Aplicativo simples para assinar PDFs com certificado digital no macOS.

---

## Pré-requisitos

- macOS com Python 3 instalado
- Certificado digital (arquivo `.p12`/`.pfx` **ou** instalado no Keychain do macOS)

---

## Instalação (primeira vez)

Abra o Terminal e execute:

```bash
pip3 install pyhanko
```

> Se não tiver o pip3, instale o Python em: https://www.python.org/downloads/

---

## Como usar

### Opção 1 — Via Terminal

```bash
cd ~/Downloads/pdf-signer
bash run.sh
```

### Opção 2 — Duplo clique

1. Abra o `run.sh` com duplo clique (pode precisar de permissão na primeira vez)
2. Ou abra o Terminal, arraste o arquivo `run.sh` para dentro e pressione Enter

---

## Passo a passo no app

1. **Arquivo PDF** → clique em "Escolher…" e selecione o PDF a assinar
2. **Certificado** → escolha uma das opções:
   - **Arquivo .p12/.pfx**: clique em "Escolher…" e selecione seu certificado digital. Informe a senha do certificado se houver.
   - **Keychain do macOS**: selecione a identidade listada automaticamente. Se não aparecer, clique em "Keychain Access" para gerenciar seus certificados.
3. **Posição** → escolha a página e onde a assinatura aparece no documento
4. Clique em **✍ Assinar PDF**
5. O arquivo assinado será salvo na mesma pasta do original com o sufixo `_assinado`

---

## Como exportar o certificado do Keychain (para usar como .p12)

1. Abra o **Keychain Access** (Acesso às Chaves)
2. Encontre seu certificado digital (categoria: "Meus Certificados")
3. Clique com botão direito → **Exportar**
4. Escolha o formato **Informações de Identidade Pessoal (.p12)**
5. Salve e use esse arquivo no app

---

## Posições disponíveis

| Nome               | Localização na página |
|--------------------|----------------------|
| Inferior Direito   | Rodapé direito       |
| Inferior Esquerdo  | Rodapé esquerdo      |
| Superior Direito   | Cabeçalho direito    |
| Superior Esquerdo  | Cabeçalho esquerdo   |
| Centro             | Centro da página     |
| Personalizado      | Coordenadas manuais  |

> Coordenadas personalizadas: formato `x1,y1,x2,y2` em pontos (1 ponto = 1/72 polegada). Página A4 = 595 × 842 pontos.

---

## Problemas comuns

**"pyhanko não encontrado"**
```bash
pip3 install pyhanko
```

**Certificado do Keychain não aparece**
- Abra o Keychain Access e verifique se o certificado está em "Meus Certificados"
- O certificado precisa ter a chave privada associada

**Erro de senha no .p12**
- Verifique se a senha está correta
- Alguns certificados sem senha: deixe o campo em branco
