# Troubleshooting

## Groq API key missing

If the tutor exits immediately or fails to generate output, confirm `GROQ_API_KEY` is set in `.env` or the current shell.

## Poppler not found

If PDF conversion fails on Windows, make sure Poppler binaries are available on `PATH` or under the bundled `poppler/` or `tools/` directories.

For a fresh Windows install, download Poppler from [Poppler for Windows](https://github.com/oschwartz10612/poppler-windows) and add its `bin` directory to `PATH`.

## Tesseract not found

If OCR fails, confirm Tesseract is installed and that Malayalam language data (`mal.traineddata`) is available.

## Empty or weak retrieval results

If answers look irrelevant, first tune the retrieval settings before rebuilding:

```powershell
python .\rag.py --student-id s100 --text "കൈകഴുകൽ എന്തുകൊണ്ട് പ്രധാനമാണ്?" \
	--retrieval-candidate-k 20 \
	--retrieval-min-similarity 0.35
```

If the candidate pool is too small or the similarity threshold is too strict, you may lose useful passages. If the threshold is too loose, irrelevant chunks can still enter the prompt.

If the corpus itself is stale or poor quality, rebuild the chunks and vector index:

```powershell
python .\pipeline\pdf_content_pipeline.py
python .\pipeline\build_vector_index.py
```

Also verify the input PDFs are actually present in `input/pdfs/`.

The retrieval layer now also deduplicates near-duplicate chunks and reranks the filtered candidates, so the result list may be shorter than the raw Chroma top-k result.

## Student profile not found

If `--student-id` fails, create the profile first:

```powershell
python .\manage_student_db.py
```

## Windows path issues

Use PowerShell paths exactly as shown in the README and docs. Prefer the PowerShell relative path style and full file paths when calling the pipeline and tutor scripts.

## Quick check list

1. Confirm `.env` exists and `GROQ_API_KEY` is set.
2. Confirm `input/pdfs/` has source files if you are using the pipeline.
3. Confirm `vectorstore/` exists after building the index.
4. Confirm `manage_student_db.py` has a student profile for the requested `--student-id`.