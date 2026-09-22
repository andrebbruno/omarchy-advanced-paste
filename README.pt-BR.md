# Advanced Paste para o Omarchy

Transforma o conteúdo da área de transferência no caminho até a janela. É a ideia do
[PowerToys Advanced Paste](https://learn.microsoft.com/windows/powertoys/advanced-paste)
portada para o [Omarchy](https://omarchy.org) — usando o menu do próprio Omarchy, com o tema
do sistema, e com a transformação por IA ligada ao agente de código que você já usa.

**`SUPER + SHIFT + V`** abre o menu. Escolha a transformação e o resultado é colado na janela
em que você estava.

*[Read in English](README.md)*

## O que ele faz

Copie qualquer coisa e cole como outra coisa:

| Grupo | Transformações |
|---|---|
| **Formatação** | texto puro · Markdown (a partir de texto formatado) · juntar linhas quebradas · limpar espaços · linha única · citação Markdown · lista com marcadores · lista numerada · bloco de código |
| **Dados** | JSON formatado · JSON minificado · JSON → CSV · CSV → tabela Markdown · CSV → JSON · escapar como string JSON |
| **Caixa** | MAIÚSCULAS · minúsculas · Cada Palavra Em Maiúscula · Frase · remover acentos · slug-com-hifens · snake_case · camelCase |
| **Linhas** | ordenar · remover duplicadas · inverter a ordem |
| **Codificação** | Base64 · URL encode/decode · separar uma URL em partes · SHA-256 · contar caracteres e palavras |
| **IA** | descreva a transformação com suas próprias palavras |

Mais duas coisas que não são transformações:

- **Colar como arquivo** — `omarchy-advanced-paste file` grava a área de transferência (texto
  *ou* imagem) em `~/Downloads` e coloca o arquivo na área de transferência, de modo que a
  próxima colagem caia em um gerenciador de arquivos ou em um diálogo de upload. Copiar uma
  imagem e abrir o menu faz isso automaticamente.
- **Contar** — caracteres, palavras, linhas e bytes, sem sair da janela.

### Markdown de verdade

"Colar como Markdown" lê o formato `text/html` da área de transferência — o que um navegador,
um editor de texto ou um app de chat deixam quando você copia texto formatado — e converte
títulos, ênfase, links, imagens, listas, código, citações e tabelas. O conversor é Python de
biblioteca padrão: sem pandoc, sem Node, sem nada para instalar.

### A transformação por IA

Qualquer coisa que você consiga descrever: *"transforme em lista"*, *"traduza para inglês"*,
*"escreva isso como mensagem de commit"*, *"extraia só os e-mails"*.

Ela roda o agente que o Omarchy já tem configurado (`omarchy default agent`) — Claude Code,
Gemini, Codex, OpenCode ou Crush — com o texto chegando pela entrada padrão. Sem chave de API
extra, sem conta, sem telemetria. Para usar outro comando, coloque-o em
`~/.config/omarchy-advanced-paste/config.json`:

```json
{ "ai_command": ["claude", "-p", "{prompt}"] }
```

## Instalação

### Arch / Omarchy

Baixe o pacote em [Releases](https://github.com/andrebbruno/omarchy-advanced-paste/releases)
e instale:

```bash
sudo pacman -U omarchy-advanced-paste-*-any.pkg.tar.zst
omarchy-advanced-paste setup     # oferece o atalho SUPER+SHIFT+V
omarchy-refresh-hyprland
```

Ou compile você mesmo:

```bash
git clone https://github.com/andrebbruno/omarchy-advanced-paste
cd omarchy-advanced-paste/packaging && makepkg -si
```

### Em qualquer outra distro

```bash
pipx install git+https://github.com/andrebbruno/omarchy-advanced-paste
```

Requisitos: Python 3.11+, `wl-clipboard` (ler e escrever na área de transferência) e `wtype`
(enviar a colagem). Os dois já vêm no Omarchy. Fora do Omarchy, o menu cai para o `gum` e,
sem ele, para uma lista numerada no terminal.

## Uso

```bash
omarchy-advanced-paste                  # o menu
omarchy-advanced-paste markdown         # uma transformação, direto para a janela
omarchy-advanced-paste json --copy-only # deixa na área de transferência, sem colar
omarchy-advanced-paste ai "como tabela" # o agente, com a sua instrução
omarchy-advanced-paste file             # guarda a área de transferência em ~/Downloads
omarchy-advanced-paste list             # todas as transformações e seus nomes
```

Também funciona como filtro comum, que é como a suíte de testes o exercita:

```bash
cat dados.csv | omarchy-advanced-paste --stdin --stdout csv-to-table
```

### O atalho

`omarchy-advanced-paste setup` acrescenta esta linha ao `~/.config/hypr/bindings.lua` (e nunca
mexe em nenhuma linha que você escreveu):

```lua
o.bind("SUPER + SHIFT + V", "Advanced paste", "omarchy-advanced-paste")
```

Vale também amarrar transformações específicas, se alguma delas for a do seu dia a dia:

```lua
o.bind("SUPER + ALT + V", "Colar como texto puro", "omarchy-advanced-paste plain")
```

## Observações

- **Só Wayland.** A leitura e a escrita passam pelo `wl-clipboard`, e a colagem é um
  `Shift+Insert` enviado com `wtype` — exatamente o que os scripts de clipboard do próprio
  Omarchy fazem, então funciona tanto em terminal quanto em aplicativo gráfico.
- **Nada sai da sua máquina**, a não ser que você escolha a transformação por IA — e, mesmo
  assim, só pelo agente que você mesmo configurou.
- **A área de transferência é substituída** pelo texto transformado. É esse o objetivo, mas
  significa que o original se foi; o gerenciador de clipboard do Omarchy
  (`SUPER + CTRL + V`) continua com ele.

## Desenvolvimento

```bash
python -m pytest tests -q      # 66 testes, nenhum compositor necessário
```

As transformações são funções puras sobre um `Clip` (texto mais HTML opcional), em
`oadvpaste/transforms.py` — é isso que as torna testáveis sem sessão Wayland. Acrescentar uma
é escrever a função e uma linha no `CATALOGUE`.

## Licença

MIT © Andre Bruno
