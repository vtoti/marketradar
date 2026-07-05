"""Motor de engenharia de preços — funções puras, sem I/O.

Calcula a margem de contribuição real de produtos e pedidos, descontando
custos variáveis, impostos, taxas do canal de venda e o rateio de custos
fixos — o mesmo princípio de plataformas como Preço Certo/Mercado Turbo.

Convenções:
    - Percentuais entram como número "humano" (6 = 6%).
    - Valores monetários em reais (float).
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Canal:
    """Canal de venda (marketplace, loja própria, venda direta...)."""
    nome: str
    comissao_pct: float = 0.0      # % sobre o preço de venda
    tarifa_fixa: float = 0.0       # R$ por venda
    frete_subsidiado: float = 0.0  # R$ por venda (custo de frete bancado)


@dataclass(frozen=True)
class Decomposicao:
    """Resultado da engenharia de preços para uma venda a um dado preço."""
    preco: float
    custo_var: float
    impostos: float
    taxas_canal: float
    fixo_rateado: float
    mc: float           # margem de contribuição (R$)
    mc_pct: float       # % do preço
    lucro: float        # líquido após rateio fixo (R$)
    lucro_pct: float    # % do preço


def custo_variavel(custo: float, frete: float = 0.0, embalagem: float = 0.0,
                   outros: float = 0.0) -> float:
    """Custo variável total por unidade."""
    return custo + frete + embalagem + outros


def rateio_fixo(total_fixos_mes: float, volume_mes: float) -> float:
    """Custo fixo embutido em cada unidade vendida."""
    return total_fixos_mes / volume_mes if volume_mes > 0 else 0.0


def decompor(preco: float, custo_var: float, aliquota_pct: float,
             canal: Canal, fixo_rateado: float = 0.0) -> Decomposicao:
    """Decompõe um preço de venda em custos, impostos, taxas e lucro."""
    impostos = preco * aliquota_pct / 100
    taxas = preco * canal.comissao_pct / 100 + canal.tarifa_fixa + canal.frete_subsidiado
    mc = preco - custo_var - impostos - taxas
    lucro = mc - fixo_rateado
    return Decomposicao(
        preco=preco, custo_var=custo_var, impostos=impostos, taxas_canal=taxas,
        fixo_rateado=fixo_rateado, mc=mc,
        mc_pct=mc / preco * 100 if preco > 0 else 0.0,
        lucro=lucro,
        lucro_pct=lucro / preco * 100 if preco > 0 else 0.0,
    )


def preco_ideal(custo_var: float, aliquota_pct: float, canal: Canal,
                margem_alvo_pct: float, fixo_rateado: float = 0.0) -> float | None:
    """Preço que entrega a margem líquida alvo (% sobre o preço).

    Resolve  P = (CV + tarifa + frete_sub + fixo) / (1 - com% - imp% - alvo%).
    Retorna None quando a soma de percentuais torna a meta impossível.
    """
    denom = 1 - canal.comissao_pct / 100 - aliquota_pct / 100 - margem_alvo_pct / 100
    if denom <= 0:
        return None
    return (custo_var + canal.tarifa_fixa + canal.frete_subsidiado + fixo_rateado) / denom


def ponto_equilibrio(total_fixos_mes: float, mc_unitaria: float) -> float | None:
    """Unidades/mês para cobrir os custos fixos. None se MC <= 0."""
    if mc_unitaria <= 0:
        return None
    return total_fixos_mes / mc_unitaria


def classificar(lucro_pct: float) -> str:
    """Faixa de saúde da margem líquida: saudável / apertado / no limite / prejuízo."""
    if lucro_pct >= 15:
        return "saudável"
    if lucro_pct >= 5:
        return "apertado"
    if lucro_pct >= 0:
        return "no limite"
    return "prejuízo"


# ---------------------------------------------------------------- pedidos ---
def analisar_pedido(pedido: dict, aliquota_pct: float, rateio_un: float,
                    canal_padrao: Canal | None = None,
                    custo_local=None) -> dict:
    """Aplica a engenharia de preços a um pedido importado do ERP.

    `pedido` segue o formato do cache do Bling:
        {total, frete, taxas: {comissao, custo_frete},
         itens: [{codigo, descricao, quantidade, valor, custo_bling}]}
    `custo_local(codigo, descricao) -> float | None` resolve custo quando o
    ERP não informa (produto cadastrado localmente). Itens sem custo algum
    entram com custo 0 e são contados em `itens_sem_custo`.
    """
    receita = float(pedido.get("total") or 0)
    itens_out, custo_prod, unidades, sem_custo = [], 0.0, 0.0, 0
    for it in pedido.get("itens") or []:
        qtd = float(it.get("quantidade") or 0)
        custo = float(it.get("custo_bling") or 0)
        fonte = "Bling"
        if custo <= 0 and custo_local is not None:
            resolvido = custo_local(it.get("codigo") or "", it.get("descricao") or "")
            if resolvido is not None and resolvido > 0:
                custo, fonte = float(resolvido), "produto local"
        if custo <= 0:
            fonte = "sem custo"
            sem_custo += 1
        custo_prod += custo * qtd
        unidades += qtd
        itens_out.append({**it, "custo_unit": custo, "fonte_custo": fonte})

    impostos = receita * aliquota_pct / 100
    taxas_erp = (float((pedido.get("taxas") or {}).get("comissao") or 0)
                 + float((pedido.get("taxas") or {}).get("custo_frete") or 0))
    if taxas_erp > 0:
        taxas, fonte_taxa = taxas_erp, "Bling"
    elif canal_padrao is not None:
        taxas = (receita * canal_padrao.comissao_pct / 100
                 + canal_padrao.tarifa_fixa + canal_padrao.frete_subsidiado)
        fonte_taxa = canal_padrao.nome
    else:
        taxas, fonte_taxa = 0.0, "—"

    mc = receita - custo_prod - impostos - taxas
    fixo = rateio_un * unidades
    lucro = mc - fixo
    return {
        "receita": receita, "custo_prod": custo_prod, "impostos": impostos,
        "taxas": taxas, "fonte_taxa": fonte_taxa, "mc": mc,
        "mc_pct": mc / receita * 100 if receita > 0 else 0.0,
        "fixo": fixo, "lucro": lucro,
        "lucro_pct": lucro / receita * 100 if receita > 0 else 0.0,
        "unidades": unidades, "itens": itens_out, "itens_sem_custo": sem_custo,
        "status": classificar(lucro / receita * 100 if receita > 0 else 0.0),
    }


def margens_por_item(analise: dict) -> list[dict]:
    """Quebra a análise de um pedido em margem POR ITEM.

    Impostos e taxas do pedido são rateados proporcionalmente à receita de
    cada item; o custo fixo, proporcionalmente à quantidade. A soma dos itens
    reproduz os totais do pedido (exceto diferenças de frete/desconto que não
    pertencem a item algum — elas ficam na visão por pedido).
    """
    itens = analise.get("itens") or []
    base = sum(float(i.get("valor") or 0) * float(i.get("quantidade") or 0)
               for i in itens)
    unidades = float(analise.get("unidades") or 0)
    out = []
    for it in itens:
        qtd = float(it.get("quantidade") or 0)
        receita = float(it.get("valor") or 0) * qtd
        share = receita / base if base > 0 else 0.0
        custo = float(it.get("custo_unit") or 0) * qtd
        impostos = analise["impostos"] * share
        taxas = analise["taxas"] * share
        fixo = analise["fixo"] * (qtd / unidades) if unidades > 0 else 0.0
        mc = receita - custo - impostos - taxas
        lucro = mc - fixo
        out.append({
            "codigo": it.get("codigo") or "", "descricao": it.get("descricao") or "",
            "quantidade": qtd, "receita": receita, "custo": custo,
            "impostos": impostos, "taxas": taxas, "mc": mc,
            "mc_pct": mc / receita * 100 if receita > 0 else 0.0,
            "fixo": fixo, "lucro": lucro,
            "lucro_pct": lucro / receita * 100 if receita > 0 else 0.0,
            "fonte_custo": it.get("fonte_custo") or "",
            "status": classificar(lucro / receita * 100 if receita > 0 else 0.0),
        })
    return out
