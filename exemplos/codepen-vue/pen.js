// Painel JS do CodePen. Usa a API estática minuto-a-minuto (CORS liberado).
const { createApp } = Vue;

const API = "https://minutoaminuto.pages.dev";
const BASE = `${API}/v1/eleicoes/2022-2t/presidente/br`;

createApp({
  data() {
    return {
      locais: [{ sigla: "BR", nome: "Brasil" }],
      local: "BR",
      eixos: [
        { id: "minuto", nome: "Por horário" },
        { id: "pct", nome: "Por % apurado" },
      ],
      eixo: "minuto",
      series: {}, // { minuto: {...}, pct: {...} } do local atual
      indice: 0,
      tocando: false,
      velocidade: 5,
      timer: null,
      erro: "",
      cor: [
        { texto: "text-teal-700", fundo: "bg-teal-600" },
        { texto: "text-orange-600", fundo: "bg-orange-500" },
      ],
    };
  },
  computed: {
    serie() {
      return this.series[this.eixo];
    },
    pontos() {
      return this.serie ? this.serie.pontos : [];
    },
    ponto() {
      return this.pontos[this.indice];
    },
    candidatos() {
      return this.serie ? this.serie.candidatos : [];
    },
    lider() {
      if (!this.ponto) return null;
      const [a, b] = this.candidatos.map((c) => c.numero);
      const va = this.ponto.votos[a];
      const vb = this.ponto.votos[b];
      return va === vb ? null : va > vb ? a : b;
    },
    faixa() {
      // Faixa vertical do gráfico ajustada aos dados (ignora o início instável, < 1% apurado),
      // sempre incluindo a linha dos 50%.
      const numero = this.candidatos[0]?.numero;
      const valores = this.pontos.filter((p) => p.pct_secoes >= 1).map((p) => this.pctValidosDe(p, numero));
      const min = Math.min(50, ...valores) - 1;
      const max = Math.max(50, ...valores) + 1;
      return { min, max };
    },
    linha() {
      const numero = this.candidatos[0]?.numero;
      return this.pontos.map((p, i) => `${this.x(i)},${this.y(this.pctValidosDe(p, numero))}`).join(" ");
    },
  },
  watch: {
    local() {
      this.carregar();
    },
  },
  async mounted() {
    const resumo = await this.buscar(`${BASE}/resumo.json`);
    if (resumo) {
      // Os links HATEOAS do resumo do Brasil listam as UFs disponíveis.
      this.locais.push(...resumo._links.filhos.map((f) => ({ sigla: f.name, nome: f.name })));
    }
    await this.carregar();
  },
  methods: {
    async buscar(url) {
      try {
        const resp = await fetch(url);
        if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
        return await resp.json();
      } catch (e) {
        this.erro = `Não foi possível carregar ${url}: ${e.message}`;
        return null;
      }
    },
    async carregar() {
      this.pausar();
      const base = this.local === "BR" ? BASE : `${BASE}/${this.local.toLowerCase()}`;
      const [minuto, pct] = await Promise.all([
        this.buscar(`${base}/serie-minuto.json`),
        this.buscar(`${base}/serie-pct.json`),
      ]);
      if (!minuto || !pct) return;
      this.series = { minuto, pct };
      this.indice = Math.min(this.indice, this.pontos.length - 1);
    },
    trocarEixo(eixo) {
      // Mantém o mesmo % apurado ao trocar de eixo.
      const pct = this.ponto ? this.ponto.pct_secoes : 0;
      this.eixo = eixo;
      const i = this.pontos.findIndex((p) => p.pct_secoes >= pct);
      this.indice = i === -1 ? this.pontos.length - 1 : i;
    },
    alternarPlay() {
      if (this.tocando) return this.pausar();
      if (this.indice >= this.pontos.length - 1) this.indice = 0;
      this.tocando = true;
      this.timer = setInterval(() => {
        if (this.indice >= this.pontos.length - 1) return this.pausar();
        this.indice = Math.min(this.indice + this.velocidade, this.pontos.length - 1);
      }, 100);
    },
    pausar() {
      this.tocando = false;
      clearInterval(this.timer);
    },
    pctValidosDe(p, numero) {
      // % dos votos válidos: só votos nominais (sem brancos e nulos).
      const validos = this.candidatos.reduce((s, c) => s + p.votos[c.numero], 0);
      return validos ? (100 * p.votos[numero]) / validos : 0;
    },
    pctValidos(numero) {
      return this.pctValidosDe(this.ponto, numero);
    },
    x(i) {
      return (600 * i) / Math.max(this.pontos.length - 1, 1);
    },
    y(pct) {
      const { min, max } = this.faixa;
      const limitado = Math.min(max, Math.max(min, pct ?? 50));
      return 160 - ((limitado - min) / (max - min)) * 160;
    },
    hora(iso) {
      return iso.slice(11, 16);
    },
    fmtPct(v) {
      return `${v.toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}%`;
    },
    fmtNum(v) {
      return v.toLocaleString("pt-BR");
    },
  },
}).mount("#app");
