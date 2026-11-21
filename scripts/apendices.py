"""Apêndices da monografia, gerados dos registros (sem números digitados à mão).

Uso: python scripts/apendices.py <dir_Post-Textual>
     (executar na raiz do repositório)

Gera:
  apendice-a-prompt.tex   o prompt completo de uma pergunta de teste em C3, em português e em inglês, remontado
                          por `build_prompt` e conferido pelo SHA-256 gravado no registro do teste
  apendice-b-bancos.tex   os 17 bancos do recorte: famílias, perguntas por partição, acurácia de C0 e C3 em
                          português e o ganho de C3 sobre C0 nos dois idiomas
"""

from __future__ import annotations

import dataclasses
import json
import sys
from collections import Counter
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src"))
from tcc_rag.data.spider import build_ddl  # noqa: E402
from tcc_rag.generation.prompt import build_prompt  # noqa: E402
from tcc_rag.schemas import Demo  # noqa: E402

ART = RAIZ / "resultados/confirmatorio/artifacts"
REGISTRO = ART / "runs-v2/confirmatorio-test-a99f7394fedc945b-fb350ed2.jsonl"
MANIFESTO = ART / "manifest.json"
ANALISE = RAIZ / "resultados/confirmatorio/analise-test-a99f7394fedc945b.json"
TABELAS = RAIZ / "data/spider/tables.json"
EXEMPLO = "spider_train_spider_3289"  # banco college_1: o mesmo item da Figura do prompt e do quadro do literal
OMITIDO = "[esquema do banco: idêntico ao da versão em português, omitido aqui]"


def esc(t: str) -> str:
    return t.replace("_", "\\_")


def num(v: float, casas: int = 1) -> str:
    return f"{v:.{casas}f}".replace(".", ",")


def sinal(v: float) -> str:
    if round(abs(v), 1) == 0:
        return num(0.0)
    return ("$+$" if v > 0 else "$-$") + num(abs(v))


def prompts() -> dict[str, tuple[str, str]]:
    tabelas = {t["db_id"]: t for t in json.loads(TABELAS.read_text(encoding="utf-8"))}
    man = {e["example_id"]: e for e in json.loads(MANIFESTO.read_text(encoding="utf-8"))["examples"]}
    campos = [f.name for f in dataclasses.fields(Demo)]
    regs = {}
    with REGISTRO.open(encoding="utf-8") as fh:
        for ln in fh:
            r = json.loads(ln)
            if r["example_id"] == EXEMPLO and r["condition"] == "C3":
                regs[r["lang"]] = r
    saida = {}
    for lang in ("pt", "en"):
        r = regs[lang]

        def demo(uid: str) -> Demo:
            eid = uid.split("::")[0]
            e = man[eid]
            kw = dict(uid=uid, example_id=eid, db_id=e["db_id"], lang=lang, question_raw=e[f"question_{lang}"],
                      question_delex="", sql=e["sql"], signature={}, tables=[])
            kw.update({c: None for c in campos if c not in kw})
            return Demo(**kw)

        ddl = build_ddl(tabelas[r["db_id"]])
        built = build_prompt(r["question_raw"], ddl, [demo(u) for u in r["prompt_demo_ids"]], lang, 4096, 320)
        if built.sha256 != r["prompt_sha256"]:
            raise SystemExit(f"prompt {lang} remontado difere do registrado")
        saida[lang] = (built.text, ddl)
    return saida


def apendice_a() -> str:
    p = prompts()
    pt, _ = p["pt"]
    en, ddl = p["en"]
    en = en.replace(ddl, OMITIDO)
    opc = "[breaklines, breakanywhere, fontsize=\\scriptsize, frame=single, framesep=2mm]"
    return (
        "\\chapter{\\textit{PROMPT} COMPLETO DE UMA PERGUNTA DO CONJUNTO DE TESTE}\\label{apx:prompt}\n\n"
        "Este apêndice reproduz, sem abreviação, o \\textit{prompt} recebido pelo modelo de linguagem na condição C3 "
        "para a pergunta de teste do banco \\texttt{college\\_1} apresentada na Figura \\ref{fig:estrutura_prompt} e "
        "no Quadro \\ref{tab:exemplo_literal}, nas versões em português brasileiro e em inglês. Os dois textos foram "
        "remontados pelo código do experimento, a partir do manifesto de dados e das demonstrações gravadas no "
        "registro do teste, e conferidos pelo resumo criptográfico (SHA-256) que o registro guarda de cada "
        "\\textit{prompt}. As linhas longas foram quebradas para caber na página. O texto é enviado ao modelo como "
        "uma única mensagem do usuário, no formato de conversa do próprio modelo, conforme a Seção \\ref{sec:Prompt}. "
        "Na versão em inglês, o esquema, idêntico ao da versão em português, foi omitido.\n\n"
        "\\section{VERSÃO EM PORTUGUÊS BRASILEIRO}\n\n"
        f"\\begin{{Verbatim}}{opc}\n{pt}\n\\end{{Verbatim}}\n\n"
        "\\section{VERSÃO EM INGLÊS}\n\n"
        f"\\begin{{Verbatim}}{opc}\n{en}\n\\end{{Verbatim}}\n"
    )


def apendice_b() -> str:
    man = json.loads(MANIFESTO.read_text(encoding="utf-8"))["examples"]
    a = json.loads(ANALISE.read_text(encoding="utf-8"))
    pb = a["por_banco"]
    cont = Counter((e["db_id"], e["partition"]) for e in man)
    fam = {d: len({e["family_id"] for e in man if e["db_id"] == d}) for d in pb}
    origem = {e["db_id"]: e["source"] for e in man}
    linhas, tot = [], Counter()
    for d in sorted(pb):
        v = pb[d]
        if v["n"] != cont[(d, "test")]:
            raise SystemExit(f"{d}: n do teste difere do manifesto")
        marca = "$^{*}$" if origem[d] == "dev" else ""
        g_pt, g_en = 100 * (v["C3|pt"] - v["C0|pt"]), 100 * (v["C3|en"] - v["C0|en"])
        linhas.append(f"\\texttt{{{esc(d)}}}{marca} & {fam[d]} & {cont[(d, 'pool')]} & {cont[(d, 'val')]} & "
                      f"{v['n']} & {num(100 * v['C0|pt'])} & {num(100 * v['C3|pt'])} & {sinal(g_pt)} & "
                      f"{sinal(g_en)} \\\\")
        for k in ("pool", "val", "test"):
            tot[k] += cont[(d, k)]
        tot["fam"] += fam[d]
    c0, c3 = a["celulas"]["C0|pt"], a["celulas"]["C3|pt"]
    c0e, c3e = a["celulas"]["C0|en"], a["celulas"]["C3|en"]
    linhas += ["\\midrule",
               f"\\textbf{{Total}} & {tot['fam']} & {tot['pool']} & {tot['val']} & {tot['test']} & "
               f"{num(100 * c0['ex'])} & {num(100 * c3['ex'])} & {sinal(100 * (c3['ex'] - c0['ex']))} & "
               f"{sinal(100 * (c3e['ex'] - c0e['ex']))} \\\\"]
    corpo = "\n".join(linhas)
    return (
        "\\chapter{BANCOS DO RECORTE E RESULTADOS POR BANCO}\\label{apx:bancos}\n\n"
        "A Tabela \\ref{tab:bancos} lista os 17 bancos do recorte de domínio único descrito na Seção "
        "\\ref{sec:ComposicaoParticoes}, com o número de famílias canônicas e de perguntas em cada partição, a acurácia "
        "de execução das condições C0 e C3 no conjunto de teste em português brasileiro e o ganho de C3 sobre C0 nos dois "
        "idiomas. Os valores por banco apoiam-se em poucas perguntas, de 22 a 42, e servem para mostrar a variação entre "
        "os bancos, discutida nas limitações do Capítulo \\ref{chp:CONCLUSAO}, e não para comparar bancos entre si.\n\n"
        "\\begin{table}[!htbp]\n\\centering\n"
        "\\caption{Bancos do recorte: partições e acurácia de execução no conjunto de teste.}\n\\footnotesize\n"
        "\\setlength{\\tabcolsep}{2pt}\n"
        "\\begin{tabular*}{\\linewidth}{@{\\extracolsep{\\fill}}lcccccccc@{}}\n\\toprule\n"
        " & & \\multicolumn{3}{c}{\\textbf{Perguntas}} & \\multicolumn{2}{c}{\\textbf{EX em PT (\\%)}} & "
        "\\multicolumn{2}{c}{\\textbf{C3 $-$ C0 (pp)}} \\\\\n"
        "\\cmidrule(lr){3-5}\\cmidrule(lr){6-7}\\cmidrule(lr){8-9}\n"
        "\\textbf{Banco} & \\textbf{Famílias} & \\textbf{Base} & \\textbf{Validação} & \\textbf{Teste} & \\textbf{C0} & "
        "\\textbf{C3} & \\textbf{PT} & \\textbf{EN} \\\\\n\\midrule\n"
        f"{corpo}\n\\bottomrule\n\\end{{tabular*}}\n"
        "\\par\\vspace{0.3\\baselineskip}\n\\parbox{\\linewidth}{\\footnotesize\\raggedright "
        "$^{*}$: banco da partição de desenvolvimento do \\textit{Spider}; os demais vêm da partição de treinamento. "
        "Base: base de demonstrações. EX: acurácia de execução; pp: pontos percentuais. As perguntas da base e da "
        "validação contam uma vez, embora existam nos dois idiomas.}\n"
        "\\vspace{0.1\\baselineskip}\n\\newline \\footnotesize \\textbf{Fonte: Autoria própria (2026).}\n"
        "\\label{tab:bancos}\n\\end{table}\n"
    )


def main(saida: Path) -> None:
    (saida / "apendice-a-prompt.tex").write_text(apendice_a(), encoding="utf-8")
    (saida / "apendice-b-bancos.tex").write_text(apendice_b(), encoding="utf-8")
    print(saida / "apendice-a-prompt.tex", saida / "apendice-b-bancos.tex")


if __name__ == "__main__":
    main(Path(sys.argv[1]))
