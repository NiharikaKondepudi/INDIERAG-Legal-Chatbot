import json
import requests

# Load benchmark queries
with open("benchmark_queries.json") as f:
    data = json.load(f)

benchmark = data["questions"]
queries = [item["query"] for item in benchmark]

print(f"Running benchmark: {data['benchmark_name']}")
print(f"Total questions: {len(benchmark)}\n")

# Call evaluation endpoint
response = requests.post("http://127.0.0.1:8000/evaluate/retrieval", 
                        json={"queries": queries, "mode": "both"})
results = response.json()

# Calculate metrics
hybrid_hits = 0
vector_hits = 0
hybrid_scores_by_category = {"easy": [], "medium": [], "hard": []}
vector_scores_by_category = {"easy": [], "medium": [], "hard": []}

print("="*80)
print("RETRIEVAL EVALUATION RESULTS")
print("="*80)

for i, item in enumerate(results):
    gold_keywords = benchmark[i]["gold_keywords"]
    difficulty = benchmark[i]["difficulty"]
    category = benchmark[i]["category"]
    
    # Check if ANY gold keyword appears in top-3 retrieved docs
    hybrid_hit = any(
        any(keyword.lower() in doc["text"].lower() for keyword in gold_keywords)
        for doc in item["hybrid_results"][:3]
    )
    
    vector_hit = any(
        any(keyword.lower() in doc["text"].lower() for keyword in gold_keywords)
        for doc in item["vector_results"][:3]
    )
    
    if hybrid_hit:
        hybrid_hits += 1
        hybrid_scores_by_category[difficulty].append(1)
    else:
        hybrid_scores_by_category[difficulty].append(0)
    
    if vector_hit:
        vector_hits += 1
        vector_scores_by_category[difficulty].append(1)
    else:
        vector_scores_by_category[difficulty].append(0)
    
    # Print per-query results
    print(f"\nQ{i+1} [{difficulty.upper()}] ({category}): {queries[i][:60]}...")
    print(f"  Hybrid Hit@3: {'✓' if hybrid_hit else '✗'}")
    print(f"  Vector Hit@3: {'✓' if vector_hit else '✗'}")
    if hybrid_hit and not vector_hit:
        print(f"  >>> HYBRID WINS")
    elif vector_hit and not hybrid_hit:
        print(f"  >>> VECTOR WINS")

# Calculate overall accuracy
hybrid_accuracy = hybrid_hits / len(benchmark)
vector_accuracy = vector_hits / len(benchmark)
improvement = (hybrid_accuracy - vector_accuracy) * 100

print("\n" + "="*80)
print("OVERALL RESULTS")
print("="*80)
print(f"Hybrid Retrieval Hit@3 Accuracy: {hybrid_accuracy*100:.1f}% ({hybrid_hits}/{len(benchmark)})")
print(f"Vector-Only Hit@3 Accuracy:      {vector_accuracy*100:.1f}% ({vector_hits}/{len(benchmark)})")
print(f"Absolute Improvement:            +{improvement:.1f}%")
print(f"Relative Improvement:            +{(improvement/vector_accuracy)*100:.1f}%")

# Breakdown by difficulty
print("\n" + "="*80)
print("BREAKDOWN BY DIFFICULTY")
print("="*80)
for diff in ["easy", "medium", "hard"]:
    if hybrid_scores_by_category[diff]:
        h_acc = sum(hybrid_scores_by_category[diff]) / len(hybrid_scores_by_category[diff]) * 100
        v_acc = sum(vector_scores_by_category[diff]) / len(vector_scores_by_category[diff]) * 100
        print(f"{diff.upper():8s}: Hybrid {h_acc:.1f}% | Vector {v_acc:.1f}% | Gain: +{h_acc-v_acc:.1f}%")

# Save results
output = {
    "benchmark_name": data["benchmark_name"],
    "total_questions": len(benchmark),
    "hybrid_accuracy": hybrid_accuracy,
    "vector_accuracy": vector_accuracy,
    "improvement_percent": improvement,
    "hybrid_hits": hybrid_hits,
    "vector_hits": vector_hits,
    "by_difficulty": {
        diff: {
            "hybrid": sum(hybrid_scores_by_category[diff]) / len(hybrid_scores_by_category[diff]) if hybrid_scores_by_category[diff] else 0,
            "vector": sum(vector_scores_by_category[diff]) / len(vector_scores_by_category[diff]) if vector_scores_by_category[diff] else 0
        }
        for diff in ["easy", "medium", "hard"]
    }
}

with open("benchmark_results.json", "w") as f:
    json.dump(output, f, indent=2)

print("\nResults saved to benchmark_results.json")
