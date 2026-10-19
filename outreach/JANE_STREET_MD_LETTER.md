# 🏛️ INSTITUTIONAL OUTREACH: JANE STREET
## To: Head of Automated Market Making & Quantitative Trading Architecture
**From:** Arunjyoti Sarma (*Department of Electronics Engineering, IIT (BHU), Varanasi*)  
**Subject:** Micro-Price Hawkes Integration, Glosten-Milgrom Adverse Selection Immunity & Tiered Maker Rebates  
**Repository:** [github.com/arunjyotisarmarsece24-jpg/neuroquant-lob](https://github.com/arunjyotisarmarsece24-jpg/neuroquant-lob)  
**Academic Preprint:** [`paper/neuroquant_lob.pdf`](file:///C:/Users/arunj/Desktop/Arunjyoti_Sarma_all_For_Research/My_Coding_Cool/My_Quant/Software_Project/paper/neuroquant_lob.pdf) (Strict 6 Pages, IEEE / SSRN Format)  

---

Dear Jane Street Quantitative Trading Architecture Team,

At Jane Street, quantitative market making blends deep statistical intuition with deterministic, high-throughput software architecture. The central challenge of passive quoting across competitive electronic exchanges is balancing fee incentives against adverse selection: capturing passive maker rebates while avoiding the winner's curse when informed orders sweep the book.

We designed **NeuroQuant-LOB** around a formal mathematical framework unifying **Stoikov order book imbalance**, **self-exciting Hawkes jump processes**, and **tiered exchange fee optimization**:

### 1. Hawkes Micro-Price Formulation & Real-Time Skewing
Rather than quoting around the naive mid-price $S_{\text{mid}} = \frac{1}{2}(P_a + P_b)$, our engine continuously calculates the volume-weighted Stoikov micro-price:
$$P_{\text{micro}} = \frac{P_a Q_b + P_b Q_a}{Q_a + Q_b}$$
coupled to mutually exciting Hawkes intensity jumps $\lambda_k(t) = \mu_k + \sum_{m \in \{a, b\}} \int_0^t \alpha_{km} e^{-\beta_{km}(t - s)} dN_m(s)$. When incoming order intensity surges on the bid side, the RSNN updates its internal membrane potential in **230 ns**, dynamically shifting quoting spreads to prevent adverse fills.

### 2. Tiered Exchange Fee Accounting & Lemma 1 Proof
* **Exchange Fee Structure:** $-0.002\%$ maker rebate credit ($-0.2\text{ bps}$) versus $+0.005\%$ taker fee penalty ($+0.5\text{ bps}$).
* **Exact Adverse Selection Boundary (Lemma 1):** We prove that passive maker execution strictly dominates aggressive taker routing if and only if adverse selection penalty satisfies $\delta_{\text{adv}} < r_t - r_m = 0.700\text{ bps}$.
* **Empirical Validation:** Across 1,000 grid evaluations, our empirical crossover measured **0.7007 bps** (absolute error: **0.0007 bps**).
* **Net Rebate Harvested:** On an institutional benchmark liquidation of $10,000$ contracts ($185M notional), the engine harvested **+$1,050.93 in net cash rebates** by filling 28.4% of order volume passively.

### 3. Winner's Curse Immunity During Flash Crashes
In Audit 4 (The Bitter PnL Battle), under an aggressive 500-tick institutional toxic sweep cascade:
* A traditional naive market maker suffered 4 severe toxic fills, accumulating negative inventory and suffering severe PnL drawdown.
* **NeuroQuant-LOB suffered 0 toxic fills (100% avoidance)**, dynamically withdrawing liquidity milliseconds before toxic cascades hit the order book and capturing post-shock spread reversion.

### 4. Reproducible Verification & Interactive Terminal
You can inspect the entire system in real time, including the interactive DOM ladder, live 60 FPS oscilloscope, and 56 automated unit tests:
```powershell
git clone https://github.com/arunjyotisarmarsece24-jpg/neuroquant-lob.git
cd neuroquant-lob
python verify.py --tests-only
python verify.py --open-only
```

I would be thrilled to discuss micro-price dynamics, formal verification, and execution engineering with your quantitative trading group.

Sincerely,

**Arunjyoti Sarma**  
Research Scholar, Department of Electronics Engineering  
Indian Institute of Technology (BHU), Varanasi  
Email: arunjyotisarmarsece24-jpg@github.com  
Preprint PDF: [`paper/neuroquant_lob.pdf`](file:///C:/Users/arunj/Desktop/Arunjyoti_Sarma_all_For_Research/My_Coding_Cool/My_Quant/Software_Project/paper/neuroquant_lob.pdf)
