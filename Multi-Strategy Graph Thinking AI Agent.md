# You Don't Need GraphRAG! Build a Multi-Strategy Graph Thinking AI Agent | by Gao Dalie (Ilyass) | in Data Science Collective - Freedium

<style>svg { fill: #ffffff }</style>

Support Freedium

Dear Freedium users,  
  
We've updated our donation options to provide you with more ways to support our mission. Your contributions are invaluable in helping us maintain and improve Freedium, ensuring we can continue to provide unrestricted access to quality content.  
  
We now offer multiple platforms for donations, including Patreon, Ko-fi, and Liberapay. Each option allows you to support us in the way that's most convenient for you.  
  
Your support, no matter the platform or amount, makes a significant difference. It allows us to cover our operational costs and invest in enhancing Freedium's features and reliability.  
  
Thank you for being a part of the Freedium community and for your continued support.  
  
Choose Your Preferred Donation Platform:

[Patreon](https://patreon.com/Freedium "Patreon") [Ko-fi](https://ko-fi.com/zhymabekroman "Ko-fi") [Liberapay](https://liberapay.com/ZhymabekRoman/ "Liberapay") Close [Source code - Codeberg](https://codeberg.org/Freedium-cfd/web "Codeberg") [Source code - GitHub](https://github.com/Freedium-cfd/web "GitHub")

[Freedium](/)

Menu

-   [ko-fi](https://ko-fi.com/zhymabekroman)
-   [librepay](https://liberapay.com/ZhymabekRoman/)
-   [patreon](https://patreon.com/Freedium)

[< Go to the original](https://medium.com/data-science-collective/you-dont-need-graphrag-build-a-multi-strategy-graph-thinking-ai-agent-a18cd2313b9d#bypass)

![Preview image](https://miro.medium.com/v2/resize:fit:700/1*r-hxIGIFy-GlL1FKKgqyCQ.png)

# You Don't Need GraphRAG! Build a Multi-Strategy Graph Thinking AI Agent

## In this Story, I have a super quick tutorial showing you how to build a Multi-Strategy Graph Thinking to build a powerful agent chatbot for…

[![Gao Dalie (Ilyass)](https://miro.medium.com/v2/resize:fill:88:88/1*drBiQzO68eWvJ_Mot-m1oQ.png)

](https://medium.com/@GaoDalie_AI "NC State Uni (Research Assistant), Learn AI Agent, LLMs, RAG & Generative AI. See everything I have to offer at the link below: https://linktr.ee/GaoDalie_AI")

[Gao Dalie (Ilyass)](https://medium.com/@GaoDalie_AI "NC State Uni (Research Assistant), Learn AI Agent, LLMs, RAG & Generative AI. See everything I have to offer at the link below: https://linktr.ee/GaoDalie_AI") [Follow](https://medium.com/@GaoDalie_AI "NC State Uni (Research Assistant), Learn AI Agent, LLMs, RAG & Generative AI. See everything I have to offer at the link below: https://linktr.ee/GaoDalie_AI")

[![Data Science Collective](https://miro.medium.com/v2/resize:fill:48:48/1*0nV0Q-FBHj94Kggq00pG2Q.jpeg)

Data Science Collective

](https://medium.com/data-science-collective "Advice, insights, and ideas from the Medium data science…")a11y-light ~10 min read · July 29, 2025 (Updated: July 29, 2025) · Free: No

In this Story, I have a super quick tutorial showing you how to build a Multi-Strategy Graph Thinking to build a powerful agent chatbot for your business or personal use.

GraphRAG, which combines knowledge graph technology with RAG, is a hot spot in the field of LLM applications in the second half of this year.

I've been spending a lot of time poking around with GraphRag, and while they're seriously cool, they've got some quirks.

One weekend, I built my own knowledge graph by creating nodes and edges, chunking the input document into tokens, recording the entities and relationships contained in each chunk, and utilising an LLM to generate the output.

Knowledge graphs can be fun, but they're often broken. My knowledge graph relies on large language model (LLM) agents for graph traversal and retrieval — an approach that's sensitive to how the traversal is initialised. It's prone to entity linking errors and may not generalise well to custom ("bring-your-own") knowledge graphs.

Many knowledge graphs are full of noisy, outdated, or missing information. It's like trying to navigate using a broken map — with wrong street names and missing roads. These systems also struggle with complex questions that require multi-hop reasoning across multiple relationships, especially in large or intricate graphs. Worse, they often ignore other useful sources like text documents, which might contain better answers.

When a knowledge graph contains too much information, it can overwhelm large language models — especially those with limited context-handling capabilities. These models also struggle with specialised topics like medicine or temporal reasoning, which often require custom retrieval and reasoning strategies.

That's where _**Bring Your Own Knowledge Graph**_ comes in. It combines multiple retrieval strategies — such as entity linking, subgraph retrieval, and Cypher query execution — to gather richer and more relevant context. It also employs scoring-based methods to minimise the number of LLM calls while enhancing performance, dynamically fetching relevant graph data and providing the language model with improved contextual grounding for reasoning.

So, let me give you a quick demo of a live chatbot to show you what I mean.

<iframe class="w-full" src="https://cdn.embedly.com/widgets/media.html?src=https%3A%2F%2Fwww.youtube.com%2Fembed%2FjSHOr5dz9l8%3Ffeature%3Doembed&amp;display_name=YouTube&amp;url=https%3A%2F%2Fwww.youtube.com%2Fwatch%3Fv%3DjSHOr5dz9l8&amp;image=https%3A%2F%2Fi.ytimg.com%2Fvi%2FjSHOr5dz9l8%2Fhqdefault.jpg&amp;type=text%2Fhtml&amp;schema=youtube" referrerpolicy="no-referrer" width="854" height="480" allowfullscreen="" frameborder="0" scrolling="no"></iframe>

I will ask the chatbot a question: "What genre of film is associated with the place where Wynton Marsalis was born?" If you take a look at how the Agent generates the output, you'll see that the agent **loads** the data from a CSV file and **prints** out how many nodes and edges the graph **contains**.

**It utilises a** knowledge graph to process the question, allowing the LLM to determine which entities, paths, and answer candidates are relevant, guided by the graph schema. It parses LLM artifacts and **uses a** fuzzy string matcher (`FuzzyStringIndex`) to connect the LLM's free-text entities to actual nodes in the graph.

Next it **uses** `EntityLinker` to match both the entities and the answer candidates back to the graph, ensuring that all reasoning is grounded in real data`AgenticRetriever`, which uses the LLM to navigate the graph intelligently. It starts from the linked entities and selects which relations to follow, and `PathRetriever` goes beyond individual triplets and follows multi-hop reasoning paths.

**Finally,** it **uses** **Bring Your Own Knowledge Graph** to wrap everything together — linking, retrieving, and generating. It takes the question, runs all the necessary steps to gather graph-grounded evidence, and uses the LLM to generate a final answer.

If you want **to** use the **algorithm** **with** another LLM **other than** Amazon Bedrock, feel free to check **out** my **[Patreon](https://www.patreon.com/GaoDalie_AI)**

#### Before we start! 🦸🏻‍♀️

If you like this topic and you want to support me:

1.  **Clap** my article 50 times; that will really help me out.👏
2.  **[Follow](https://medium.com/@mr.tarik098)** me on Medium and subscribe to get my latest article for Free🫶
3.  Join the family — Subscribe to the **[YouTube channel](https://www.youtube.com/channel/UC6P5WCWjqhhXVFBqbJHNxyw)**

### What is BYOKG RAG?

**"BYOKG (Bring Your Own Knowledge Graph)"** is a framework designed to enhance knowledge graph question answering (KGQA) by integrating diverse external knowledge sources with large language models (LLMs). It leverages multiple graph retrieval strategies — including entity linking, subgraph extraction, and Cypher query execution — to gather relevant contextual information from various knowledge graphs.

BYOKG aims to enhance the accuracy, robustness, and generalisation of KGQA systems by integrating these retrieval techniques with the reasoning capabilities of LLMs, thereby enabling more precise and contextually grounded answers across diverse domains and knowledge bases.

### How does it work?

![None](https://miro.medium.com/v2/resize:fit:700/1*ejgup71_8IDENxXPkvqjpQ.png)

As shown in the figure above, the **BYOKG** architecture consists of two core components: **KG-Linker** and **Graph Retrievers.**

**KG-Linker** is the core LLM-based component of the BYOKG-RAG framework that generates diverse graph artifacts instead of directly traversing knowledge graphs.

Given a user query, graph schema, and optional context, it uses a single LLM call to produce four key artifacts: extracted entities from the question, plausible relationship paths connecting those entities, executable graph queries (like OpenCypher), and draft candidate answers.

Path to Dir: \[Link\]

**Graph Retrievers** are the specialised toolkit in BYOKG-RAG that takes KG-Linker's generated artifacts and performs actual graph operations on the knowledge graph.

It uses four main components: **Entity Linking** (maps entities to a graph using string/embedding matching), **Path Retrieval** (executes relation paths via graph traversal), **Graph Query Retrieval** (runs executable queries like OpenCypher), and **Triplet Retrieval** (finds relevant facts through agentic exploration or semantic scoring).

Path to Dir: \[Link\]

### BYOKG RAG Vs GraphRag

BYOKG-RAG and GraphRAG are both frameworks for enhancing knowledge graph question answering, but they differ in design and flexibility.

BYOKG-RAG uses a multi-strategy retrieval approach — combining entity linking, agentic traversal, graph reranking, and text-based retrieval — that dynamically adapts to different KG structures and question types.

It is optimised for zero-shot and few-shot settings, requiring minimal training data, and includes a self-termination mechanism to stop retrieval once enough information is gathered.

In contrast, GraphRAG relies on supervised or fine-tuned retrievers trained on large labelled datasets to fetch relevant subgraphs in a single, static step. While GraphRAG can achieve high precision when trained effectively, it is less adaptable to new KGs or question types and often demands higher training costs.

### Let's start coding?

Before we dive into our application, we will create an ideal environment for the code to work. For this, we need to install the necessary Python libraries.

First, we will install the libraries that support the model. For this, we will do a pip install requirements. Since the demo uses the Claude models, you must first set the Claude API Key.

Copy`pip install requirements`

The next step is the usual one, where we will import the relevant libraries, the significance of which will become evident as we proceed.

We initiate the code by importing classes from

The `LocalKGStore` class provides an interface to work with the knowledge graph

### Graph Store

Copy`from graphrag_toolkit.byokg_rag.graphstore import LocalKGStore  graph_store = LocalKGStore() graph_store.read_from_csv('freebase_tiny_kg.csv') # Print graph statistics schema = graph_store.get_schema() number_of_nodes = len(graph_store.nodes()) number_of_edges = len(graph_store.get_triplets()) print(f"The graph has {number_of_nodes} nodes and {number_of_edges} edges.")  # Let's also see neighbor edges of node "Wynton Marsalis" import random sample_triplets = graph_store.get_one_hop_edges(["Wynton Marsalis"]) sample_triplets = random.sample(list(sample_triplets["Wynton Marsalis"].items()), 3) print("Some neighboring edges of node 'Wynton Marsalis' are: ", sample_triplets)`

They used a local knowledge graph to manage the knowledge graph data structure. I then read the data from the CSV file, which contains the structured triples (head, relation, tail) that define the knowledge graph.

They inspect the graph to extract the schema and calculate basic statistics, then they focus on the node `"Wynton Marsalis"` and retrieved its direct neighbours using the `get_one_hop_edges()` method.

This function returns all the edges connected to the node within one hop. They used Python `random.sample()` to randomly select three of these neighboring edges. Finally, I printed out these selected edges to showcase sample relationships connected to "Wynton Marsalis."

### KG Linker

Copy`question = "What genre of film is associated with the place where Wynton Marsalis was born?" answer = "Backstage Musical"  from graphrag_toolkit.byokg_rag.graph_connectors import KGLinker from graphrag_toolkit.byokg_rag.llm import BedrockGenerator  # Initialize llm llm_generator = BedrockGenerator(                 model_name='us.anthropic.claude-3-5-sonnet-20240620-v1:0',                 region_name='us-west-2')  kg_linker = KGLinker(graph_store=graph_store, llm_generator=llm_generator) response = kg_linker.generate_response(                 question=question,                 schema=schema,                 graph_context="Not provided. Use the above schema to understand the graph."             ) response  artifacts = kg_linker.parse_response(response) artifacts`

They ask the question, _"What genre of film is associated with the place where Wynton Marsalis was born?"_ The expected answer was _"Backstage Musical."_ My goal was to enable the system to reason across multiple hops in the graph using semantic understanding from the LLM.

They use BedrockGenerator to connect to Amazon Bedrock and use the Claude 3.5 Sonnet model hosted in the `us-west-2` region.

They built an `GLinker` instance that connects the graph data with LLM. The `KGLinker` serves as a bridge between structured knowledge and natural language understanding. I passed in the question, the graph schema (which outlines how entities and relations are organised), and a default message saying no explicit graph context is provided — encouraging the model to rely on schema-based reasoning.

They generate a structured LLM response using `generate_response`, which attempts to extract relevant paths or reasoning steps based on the question and parse the response, which extracted those meaningful artifacts such as entity paths or subgraph structures.

### Entity Linking

Copy`from graphrag_toolkit.byokg_rag.indexing import FuzzyStringIndex from graphrag_toolkit.byokg_rag.graph_retrievers import EntityLinker  # Add graph nodes text for string matching string_index = FuzzyStringIndex() string_index.add(graph_store.nodes()) retriever = string_index.as_entity_matcher() entity_linker = EntityLinker(retriever=retriever)  linked_entities = entity_linker.link(artifacts["entity-extraction"], return_dict=False) linked_answers = entity_linker.link(artifacts["draft-answer-generation"], return_dict=False) linked_entities, linked_answers`

They create an entity linking pipeline to connect free-text mentions from the LLM output back to actual nodes in the knowledge graph.

Then they developed the fuzzy matching capability by initialising a`FuzzyStringIndex`, which builds an index of all the graph node names from the `graph_store and` retriever function, and from this index using`as_entity_matcher()`, which transforms the fuzzy index into a callable tool for entity resolution. I then created a `EntityLinker` using this retriever. The `EntityLinker` is responsible for converting LLM-generated entities into actual graph node IDs, enabling grounded graph traversal and reasoning.

after that they made the linker process both the `"entity-extraction"` and `"draft-answer-generation"` artifacts returned by the LLM in the earlier step. These artifacts contain names of entities and answer candidates that need to be matched to graph nodes. By passing them through the `link()` method.

### Triplet Retrieval

Copy`from graphrag_toolkit.byokg_rag.graph_retrievers import AgenticRetriever from graphrag_toolkit.byokg_rag.graph_retrievers import GTraversal, TripletGVerbalizer graph_traversal = GTraversal(graph_store) graph_verbalizer = TripletGVerbalizer() triplet_retriever = AgenticRetriever(     llm_generator=llm_generator,      graph_traversal=graph_traversal,     graph_verbalizer=graph_verbalizer)  triplet_context = triplet_retriever.retrieve(query=question, source_nodes=linked_entities) triplet_context`

Next, they designed a triplet retriever that can reason over the knowledge graph by simulating an agent navigating from one entity to another based on the question's intent. and developed an agentic retriever which combines an LLM with graph traversal tools.

To start, I initialised `GTraversal`, which gives the system the ability to walk through the knowledge graph starting from a given set of entities. They also built a`TripletGVerbalizer`, which turns each retrieved triplet (head, relation, tail) into a format that the LLM can easily understand and evaluate.

Then they create triplet\_context `retrieve()` with the original question and the answer `linked_entities` as starting points. This method returned a set of triplets — each representing a meaningful fact or path — that the LLM believes are most useful to answer the question.

### Path Retrieval

Copy``from graphrag_toolkit.byokg_rag.graph_retrievers import PathRetriever from graphrag_toolkit.byokg_rag.graph_retrievers import GTraversal, PathVerbalizer graph_traversal = GTraversal(graph_store) path_verbalizer = PathVerbalizer() path_retriever = PathRetriever(     graph_traversal=graph_traversal,     path_verbalizer=path_verbalizer)  metapaths = [[component.strip() for component in path.split("->")] for path in artifacts["path-extraction"]] shortened_paths = [] for path in metapaths:     if len(path) > 1:         shortened_paths.append(path[:1]) for path in metapaths:     if len(path) > 2:         shortened_paths.append(path[:2]) metapaths += shortened_paths path_context = path_retriever.retrieve(linked_entities, metapaths, linked_answers) path_context  context = list(set(triplet_context + path_context)) print(f"Success! Ground-truth answer `{answer}` retrieved!") if answer in '\n'.join(context) else print("Failure..")``

They create a path-based reasoning system that leverages metapaths — structured sequences of relations — to dig deeper into the knowledge graph and extract meaningful paths between entities.

Then they use PathRetriever to require both a `graph_traversal` component and a `PathVerbalizer`. I reused the same `GTraversal` instance from before to walk through the graph, and initialised it `Path verbalizer` to convert retrieved paths into a human-readable form that the LLM can interpret. I generated metapaths from the LLM's output and added shorter versions to capture partial patterns.

They then retrieved relevant paths connecting the question entities to potential answers. Finally, they combined these with earlier triplet results and checked if the correct answer, _"Backstage Musical,"_ appeared — marking the retrieval as a success or failure.

### BYOKG RAG

Copy``from graphrag_toolkit.byokg_rag.byokg_query_engine import ByoKGQueryEngine byokg_query_engine = ByoKGQueryEngine(     graph_store=graph_store,     kg_linker=kg_linker,     triplet_retriever=triplet_retriever,     path_retriever=path_retriever,     entity_linker=entity_linker ) retrieved_context = byokg_query_engine.query(question) answers, response = byokg_query_engine.generate_response(question, "\n".join(retrieved_context))  print("Retrieved context: ", "\n".join(retrieved_context)) print("Generated answers: ", answers) print(f"Success! Ground-truth answer `{answer}` retrieved!") if answer in '\n'.join(answers) else print("Failure..")``

Finally, they built a full Bring Your custom Knowledge Graph -RAG pipeline`ByoKGQueryEngine`, which combines all components—graph store, linkers, and retrievers—to handle natural language questions. It retrieves relevant graph context and generates answers. I ran it on the question and checked if the correct answer _"Backstage Musical"_ appeared. If found, it's a success; otherwise, a failure.

### Conclusion :

BYOKG-RAG significantly advances knowledge graph question answering by integrating multiple retrieval strategies with large language models. Through extensive experiments across diverse benchmarks, it demonstrates superior performance and generalization without relying on training data, highlighting the importance of iterative and multi-strategy graph retrieval methods.

_**🧙‍♂️ I am an AI Generative expert! If you want to collaborate on a project, drop an**_ _**[inquiry here](https://docs.google.com/forms/d/e/1FAIpQLSelxGSNOdTXULOG0HbhM21lIW_mTgq7NsDbUTbx4qw-xLEkMQ/viewform)**_ _**or Book a**_ _**[1-on-1 Consulting](https://calendly.com/gao-dalie/ai-consulting-call)**_ _**Call With Me.**_

[

## I Tried LangGraph + Kimi K2 + Context Engineering & I’m REALLY Impressed!

### In this Story, I have a super quick tutorial showing you how to create a multi-agent chatbot using LangGraph, Context…

medium.com



](https://medium.com/data-science-collective/i-tried-langgraph-kimi-k2-context-engineering-im-really-impressed-cc1f04e7b270)

[

## LangChain Upgraded Library Every AI Engineer Should Know

### In this video, I’ve got a super quick tutorial showing you how to create a multi-agent chatbot using the Latest…

towardsai.net



](https://pub.towardsai.net/langchain-upgraded-library-every-ai-engineer-should-know-2fa64652dcb5)

[

## LightRag (Upgraded) + Multimodal RAG Just Revolutionized AI Forever

### In this Story, I have a super quick tutorial showing you how to create a multi-agent chatbot using LightRag and…

medium.com



](https://medium.com/data-science-collective/lightrag-upgraded-multimodal-rag-just-revolutionized-ai-forever-a1218edac8e0)

[#data-science](https://medium.com/tag/data-science "Data Science")[#machine-learning](https://medium.com/tag/machine-learning "Machine Learning")[#artificial-intelligence](https://medium.com/tag/artificial-intelligence "Artificial Intelligence")[#programming](https://medium.com/tag/programming "Programming")[#technology](https://medium.com/tag/technology "Technology")

<style>.main-content { letter-spacing: -0.06px; font-family: source-serif-pro, Georgia, Cambria, "Times New Roman", Times, serif; } pre { font-size: 75%; background-color: #e3e2e2; } p code, ul code, li code { font-size: 75%; } </style> <script>document.addEventListener('DOMContentLoaded', (event) => { hljs.highlightAll(); document.querySelectorAll('pre code').forEach((el) => { code = el.textContent; el = el.parentElement; el.innerHTML = '<button class="p-1 bg-gray-300 hljs-copy dark:bg-zinc-800">Copy</button>' + el.innerHTML; // append copy button el.getElementsByClassName('hljs-copy')[0].contentCopy = code; el.getElementsByClassName('hljs-copy')[0].addEventListener("click", function () { this.innerText = 'Copying..'; if (!navigator.userAgent.toLowerCase().includes('safari')) { navigator.clipboard.writeText(this.contentCopy); } else { prompt("Clipboard (Select: ⌘+a > Copy:⌘+c)", this.contentCopy); } this.innerText = 'Copied!'; button = this; setTimeout(function () { button.innerText = 'Copy'; }, 1500) }); }); }); </script> <style>.hljs-copy { float: right; cursor: pointer; }</style>

# Reporting a Problem

Sometimes we have problems displaying some Medium posts.  
  

If you have a problem that some images aren't loading - try using VPN. Probably you have problem with access to Medium CDN (or fucking Cloudflare's bot detection algorithms are blocking you).

Problem Description

Submit Cancel

<script>tailwind.config = { darkMode: 'class', } function changeTheme(themeName) { // Source: https://stackoverflow.com/questions/59257368/how-to-dynamically-change-the-theme-using-highlight-js console.log(`Applying theme: ${themeName}`); const existingLink = document.querySelector('link[href*="highlight.js"]'); if (existingLink) { existingLink.remove(); } const link = document.createElement("link"); link.rel = "stylesheet"; link.href = `https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.9.0/styles/${themeName}.min.css`; document.head.appendChild(link); document.querySelector("span").textContent = themeName; } function navigateToOrigin() { window.location.href = window.location.origin; } function updateThemeIcons() { const isDarkMode = localStorage.theme === 'dark' || (!('theme' in localStorage) && window.matchMedia('(prefers-color-scheme: dark)').matches); document.getElementById('darkIcon').classList.toggle('hidden', !isDarkMode); document.getElementById('lightIcon').classList.toggle('hidden', isDarkMode); } updateThemeIcons(); document.getElementById('darkModeToggle').addEventListener('click', function () { const isDarkMode = localStorage.theme === 'dark' || (!('theme' in localStorage) && window.matchMedia('(prefers-color-scheme: dark)').matches); if (isDarkMode) { document.documentElement.classList.remove('dark'); document.documentElement.style.cssText = "--lightense-backdrop: white;"; localStorage.setItem("theme", "light"); changeTheme("a11y-light"); } else { document.documentElement.classList.add('dark'); document.documentElement.style.cssText = "--lightense-backdrop: black;"; localStorage.setItem("theme", "dark"); changeTheme("androidstudio"); } updateThemeIcons(); }) if (localStorage.theme === 'dark' || (!('theme' in localStorage) && window.matchMedia('(prefers-color-scheme: dark)').matches)) { document.documentElement.classList.add('dark'); //document.getElementById('darkIcon').classList.remove('hidden'); //document.getElementById('lightIcon').classList.add('hidden') changeTheme("androidstudio"); } else { document.documentElement.classList.remove('dark') //document.getElementById('lightIcon').classList.remove('hidden'); //document.getElementById('darkIcon').classList.add('hidden'); changeTheme("a11y-light"); } </script> <script>const openModalButton = document.getElementById('openProblemModal'); const closeModalButton = document.querySelector('.modal-close'); const modal = document.getElementById('problemModal'); const problemDescriptionInput = document.getElementById('problem-description'); const submitButton = document.querySelector('form button'); const body = document.querySelector('body'); openModalButton.addEventListener('click', () => { body.classList.add('!overflow-hidden'); // Prevent scrolling on the body modal.classList.remove('hidden'); }); closeModalButton.addEventListener('click', () => { body.classList.remove('!overflow-hidden'); // Re-enable scrolling on the body modal.classList.add('hidden'); }); modal.addEventListener('click', (e) => { if (e.target === modal) { modal.classList.add('hidden'); body.classList.remove('!overflow-hidden'); } }); function navigateNoCache() { window.location.href = `/render-no-cache${window.location.pathname}`; } const submitForm = async (event) => { event.preventDefault(); console.log('Form submiting is started!'); submitButton.disabled = true; // Get the problem description from the input field const problemDescription = problemDescriptionInput.value; const currentPage = window.location.href; try { // Send a POST request to the "report-problem" API endpoint const response = await fetch('/report-problem', { method: 'POST', headers: { 'Content-Type': 'application/json', }, body: JSON.stringify({ description: problemDescription, page: currentPage }), }); if (response.ok) { // Report submitted successfully, you can add a success message or further actions here console.log('Problem report submitted successfully.'); modal.classList.add('hidden'); // Close the modal } else { // Handle errors, such as non-200 responses console.error('Failed to submit problem report.'); submitButton.disabled = false; } } catch (error) { // Handle network errors or other exceptions console.error('An error occurred:', error); submitButton.disabled = false; } }; document.getElementById('problem-form').onsubmit = submitForm; </script> <script>const h = document.documentElement, b = document.body; const st = 'scrollTop'; const sh = 'scrollHeight'; const progress = document.getElementById('progress'); const header = document.getElementById('header'); const navcontent = document.getElementById('nav-content'); document.addEventListener('scroll', function () { /* Refresh scroll % width */ const scroll = (h[st] || b[st]) / ((h[sh] || b[sh]) - h.clientHeight) * 100; progress.style.setProperty('--scroll', scroll + '%'); /* Apply classes for slide in bar */ const shouldAddClass = window.scrollY > 10; }); document.getElementById('nav-toggle').onclick = function () { document.getElementById("nav-content").classList.toggle("hidden"); } window.addEventListener('load', function () { Lightense('img:not(.no-lightense)'); }, false); </script> <script>function navigateToOrigin() { window.location.href = window.location.origin; } </script> <script>document.addEventListener('DOMContentLoaded', () => { const notificationContainer = document.querySelector('.notification-container'); const closeButton = document.querySelector('.close-button'); const notificationFlagString = "showNotification-kdjfn32" const body = document.querySelector('body'); function showNotification() { if (!localStorage.getItem(notificationFlagString)) { notificationContainer.style.display = 'block'; body.classList.add('!overflow-hidden'); } } function hideNotification() { localStorage.setItem(notificationFlagString, 'false'); notificationContainer.style.display = 'none'; body.classList.remove('!overflow-hidden'); } closeButton.addEventListener('click', () => { hideNotification(); }); // showNotification(); });</script>

<script defer="" src="https://static.cloudflareinsights.com/beacon.min.js/vcd15cbe7772f49c399c6a5babf22c1241717689176015" integrity="sha512-ZpsOmlRQV6y907TI0dKBHq9Md29nnaEIPlkf84rnaERnq6zvWvPUqr2ft8M1aS28oN72PdrCzSjY4U6VaAw1EQ==" data-cf-beacon="{&quot;rayId&quot;:&quot;970f0494ad2f11ac&quot;,&quot;version&quot;:&quot;2025.8.0&quot;,&quot;r&quot;:1,&quot;token&quot;:&quot;6cd52986ae8c4f61a1990bad97c58766&quot;,&quot;serverTiming&quot;:{&quot;name&quot;:{&quot;cfExtPri&quot;:true,&quot;cfEdge&quot;:true,&quot;cfOrigin&quot;:true,&quot;cfL4&quot;:true,&quot;cfSpeedBrain&quot;:true,&quot;cfCacheStatus&quot;:true}}}" crossorigin="anonymous"></script>