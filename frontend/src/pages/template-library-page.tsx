import { useState, useEffect } from "react";
import { useNavigate, Link } from "react-router-dom";
import { templatesApi, TemplateListItem } from "@/lib/api";
import { TemplateSearchBar } from "@/components/templates/TemplateSearchBar";
import { TemplateFilters } from "@/components/templates/TemplateFilters";
import { TemplateGrid } from "@/components/templates/TemplateGrid";
import { Button } from "@/components/ui/button";

export function TemplateLibraryPage() {
  const navigate = useNavigate();
  const [search, setSearch] = useState("");
  const [category, setCategory] = useState("");
  const [visibility, setVisibility] = useState("");
  const [templates, setTemplates] = useState<TemplateListItem[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const limit = 20;

  useEffect(() => {
    fetchLibrary();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [search, category, visibility, page]);

  const fetchLibrary = async () => {
    setIsLoading(true);
    setError(null);
    try {
      const token = localStorage.getItem("templateos_access_token") || "";
      const data = await templatesApi.getLibrary(token, {
        search,
        category,
        visibility,
        page,
        limit,
      });
      setTemplates(data.templates);
      setTotal(data.total);
    } catch (err: any) {
      setError(err.message || "Failed to fetch templates");
      setTemplates([]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleClearAll = () => {
    setSearch("");
    setCategory("");
    setVisibility("");
    setPage(1);
  };

  const hasFilters = search !== "" || category !== "" || visibility !== "";

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
        <div>
          <h1 className="text-2xl font-semibold">Template Library</h1>
          <p className="mt-1 text-sm text-slate-600">
            Browse and discover reusable document templates
          </p>
        </div>
        <Link to="/upload-template">
          <Button>Upload Template</Button>
        </Link>
      </div>

      <div className="space-y-4">
        <TemplateSearchBar value={search} onChange={(val) => { setSearch(val); setPage(1); }} />
        <TemplateFilters
          category={category}
          visibility={visibility}
          onCategoryChange={(val) => { setCategory(val); setPage(1); }}
          onVisibilityChange={(val) => { setVisibility(val); setPage(1); }}
          onClearAll={handleClearAll}
        />

        {hasFilters && (
          <div className="flex items-center text-sm text-slate-600 bg-slate-50 px-4 py-2 rounded-md">
            <span>
              Showing results
              {search && <span> for "{search}"</span>}
              {(category || visibility) && <span> in </span>}
              {category && <span className="capitalize">{category}</span>}
              {category && visibility && <span> / </span>}
              {visibility && <span className="capitalize">{visibility}</span>}
            </span>
            <button
              onClick={handleClearAll}
              className="ml-auto text-blue-600 hover:underline"
            >
              Clear all
            </button>
          </div>
        )}
      </div>

      {error ? (
        <div className="p-4 rounded-md bg-red-50 text-red-800 border border-red-200 flex flex-col items-start gap-3">
          <p>{error}</p>
          <Button variant="outline" size="sm" onClick={fetchLibrary} className="bg-white">
            Retry
          </Button>
        </div>
      ) : (
        <>
          <TemplateGrid
            templates={templates}
            onCardClick={(id) => navigate(`/templates/${id}`)}
            isLoading={isLoading}
          />

          {total > limit && (
            <div className="flex items-center justify-between border-t pt-6 mt-6">
              <span className="text-sm text-slate-500">
                Page {page} of {Math.ceil(total / limit)}
              </span>
              <div className="flex gap-2">
                <Button
                  variant="outline"
                  onClick={() => setPage(p => Math.max(1, p - 1))}
                  disabled={page === 1}
                >
                  Previous
                </Button>
                <Button
                  variant="outline"
                  onClick={() => setPage(p => p + 1)}
                  disabled={page >= Math.ceil(total / limit)}
                >
                  Next
                </Button>
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}
