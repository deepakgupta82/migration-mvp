# generate_agentic_matrix_svg.py
# Creates an editable 1400×1100 AgenticMatrix_full.svg
# Font: Segoe UI  •  Palette: corporate blue gradient  •  Fully editable in PowerPoint

import xml.etree.ElementTree as ET

WIDTH, HEIGHT = 1400, 1100
font = "Segoe UI"

def rect(x,y,w,h,fill="#ffffff",stroke="#CBD5E1",rx=4):
    e = ET.Element("rect", x=str(x), y=str(y), width=str(w), height=str(h),
                   fill=fill, stroke=stroke, **({"rx":str(rx)} if rx else {}))
    return e

def text(x,y,txt,size=12,weight="normal",fill="#1E293B"):
    t = ET.Element("text", x=str(x), y=str(y), fill=fill,
                   **{"font-family":font, "font-size":str(size),
                      "font-weight":weight})
    t.text = txt
    return t

svg = ET.Element("svg", xmlns="http://www.w3.org/2000/svg",
                 width=str(WIDTH), height=str(HEIGHT))

# gradient defs
defs = ET.SubElement(svg, "defs")
grad = ET.SubElement(defs, "linearGradient", id="gradHeader",
                     x1="0", y1="0", x2="1", y2="0")
ET.SubElement(grad, "stop", offset="0%", **{"stop-color":"#1E3A8A"})
ET.SubElement(grad, "stop", offset="100%", **{"stop-color":"#0EA5E9"})

# header
svg.append(rect(0,0,WIDTH,120,fill="url(#gradHeader)",stroke="none",rx=0))
svg.append(text(40,70,"Unified Cloud Transformation — Agentic Matrix",
                size=26,weight="600",fill="#ffffff"))
svg.append(text(40,95,"Agentic Framework • 4×3 Matrix • Continuous Optimize",
                size=13,fill="#ffffff"))

# column headers
cols = ["Baselining","Envisioning","Derivating"]
for i,cname in enumerate(cols):
    x = 260 + i*360
    svg.append(rect(x,160,340,40,fill="#E0E7FF",stroke="#93C5FD"))
    svg.append(text(x+10,185,cname,size=13,weight="600"))

# row headers
rows = ["Strategy","Technology","Financial Value","People & Org"]
for r,rname in enumerate(rows):
    y = 220 + r*200
    svg.append(rect(20,y,220,180,fill="#DBEAFE",stroke="#93C5FD"))
    svg.append(text(40,y+25,rname,size=13,weight="600"))

# grid cells (placeholders; you can fill real data below)
for r in range(4):
    for c in range(3):
        x = 260 + c*360
        y = 220 + r*200
        svg.append(rect(x,y,340,180,fill="#ffffff",stroke="#CBD5E1"))
        svg.append(text(x+10,y+25,f"Objective {r+1}.{c+1}",size=12,weight="600"))
        svg.append(text(x+10,y+45,"• bullet one",size=11))
        svg.append(text(x+10,y+60,"• bullet two",size=11))
        svg.append(text(x+10,y+75,"Agents: ExampleAgent, Optimizer",size=10,fill="#334155"))
        svg.append(text(x+10,y+90,"Artifacts: Doc1, Doc2",size=10,fill="#475569"))

# framework band
svg.append(rect(260,130,1080,25,fill="#EFF6FF",stroke="#93C5FD"))
svg.append(text(270,148,"Agentic Framework: Orchestrator • Policy Engine • Evidence Store • FinOps Guardrails",
                size=11,fill="#1E40AF"))

# optimize band
svg.append(rect(260,1030,1080,25,fill="#ECFDF5",stroke="#6EE7B7"))
svg.append(text(270,1047,"Continuous Optimize: Rightsize • Chaos/Perf • Cost Anomalies • Refactor Suggestions",
                size=11,fill="#065F46"))

# footer
svg.append(text(40,1080,"Security-by-Design • Compliance-by-Default • Agentic & Evidence-Driven © Unified IP",
                size=11,fill="#64748B"))

ET.ElementTree(svg).write("AgenticMatrix_full.svg", encoding="utf-8", xml_declaration=True)
print("✅ File generated: AgenticMatrix_full.svg")
