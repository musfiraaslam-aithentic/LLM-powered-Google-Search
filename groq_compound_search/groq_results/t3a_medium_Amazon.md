## t3a.medium – Amazon EC2 Instance  

Below is a consolidated view of the **t3a.medium** instance specifications, pricing, and performance details gathered from multiple reputable sources.

| Category | Detail |
|----------|--------|
| **Instance Family** | General‑purpose (T3a) |
| **Generation** | Current (T3a) |
| **vCPUs** | 2 |
| **Memory** | 4 GiB |
| **Processor** | AMD EPYC 7571 (x86_64) |
| **Clock Speed** | 2.2 GHz (base) – up to 2.5 GHz turbo on burst |
| **Threads per Core** | 2 |
| **Burstable Performance** | Yes (CPU credits) |
| **Network Performance** | Up to **5 Gigabit** (baseline) |
| **Enhanced Networking (ENA)** | Required / Supported |
| **Maximum Network Interfaces** | 3 |
| **Maximum Network Cards** | 1 |
| **IPv4 Addresses per Interface** | 6 |
| **IPv6 Addresses per Interface** | 6 |
| **IPv6 Support** | Yes |
| **EBS‑Optimized** | Supported (default) |
| **EBS Bandwidth** | Baseline 350 Mbps – Max 2.085 Gbps |
| **EBS Throughput** | Baseline 43.75 MB/s – Max 260.6 MB/s |
| **Maximum IOPS** | Up to 11 800 (max) |
| **Storage** | EBS‑only (no instance‑store) |
| **Hypervisor** | Nitro |
| **Virtualization Type** | HVM |
| **Supported Tenancies** | Shared (default) – can be dedicated |
| **Supported Usage Classes** | On‑Demand, Spot, Reserved (1‑yr, 3‑yr) |
| **Typical Use Cases** | Web sites, dev/test environments, micro‑services, small‑to‑medium databases, code repositories, business apps |

### Pricing (US East (N. Virginia) – example)

| Pricing Model | Price (USD/hr) |
|---------------|----------------|
| On‑Demand | **$0.0376** |
| Spot (average) | **$0.016** |
| 1‑Year Reserved (No Upfront) | **$0.024** |
| 3‑Year Reserved (No Upfront) | **$0.016** |

> Prices vary by region and may change; consult the AWS pricing page for the latest rates.

### Performance Summary

| Metric | Value |
|--------|-------|
| **Baseline Bandwidth** | 350 Mbps |
| **Baseline Throughput** | 43.75 MB/s |
| **Maximum Bandwidth** | 2.085 Gbps |
| **Maximum Throughput** | 260.6 MB/s |
| **Maximum IOPS** | 11 800 |

### Sources (References)

1. **CloudZero Advisor – t3a.medium Specs & Pricing**  
   <https://advisor.cloudzero.com/aws/ec2/t3a.medium>
2. **CloudPrice – t3a.medium specifications**  
   <https://cloudprice.net/aws/ec2/instances/t3a.medium>
3. **CostCalc (CloudOptimo) – t3a.medium pricing & specs**  
   <https://costcalc.cloudoptimo.com/aws-pricing-calculator/ec2/t3a.medium>
4. **AWS Documentation – General‑purpose (GP) instance types**  
   <https://docs.aws.amazon.com/ec2/latest/instancetypes/gp.html>
5. **Vantage Instances – t3a.medium details**  
   <https://instances.vantage.sh/aws/ec2/t3a.medium>
6. **AWS Official EC2 Instance Types – T3 family**  
   <https://aws.amazon.com/ec2/instance-types/t3/>
7. **CloudZero Comparison – T3 vs T3a vs T4g**  
   <https://www.cloudzero.com/advisor/t3-vs-t3a-vs-t4g/>

---

### Quick Take‑away

- **t3a.medium** is a cost‑effective, burstable‑performance instance with **2 vCPUs**, **4 GiB RAM**, and **up to 5 Gbps network**.  
- It uses an **AMD EPYC 7571** processor, making it roughly **10 % cheaper** than the comparable Intel‑based **t3.medium** while delivering similar performance.  
- Ideal for lightweight workloads such as web servers, development environments, and small databases.
