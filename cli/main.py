import asyncio
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

from config.settings import get_config
from core.csv_handler import export_suggestions_to_csv, import_products_from_csv
from core.product_manager import ProductManager
from data import db

app = typer.Typer(help="ikas SEO Optimizer - CLI")
console = Console()


def score_color(score: int) -> str:
    if score >= 70:
        return "green"
    if score >= 40:
        return "yellow"
    return "red"


@app.command()
def analyze(
    threshold: int = typer.Option(100, help="Skor esik degeri"),
    source: str = typer.Option("api", help="Veri kaynagi: api veya csv"),
    file: Optional[str] = typer.Option(None, help="CSV dosya yolu"),
    product_id: Optional[str] = typer.Option(None, help="Tek urun ID"),
) -> None:
    """Urunleri SEO analizi yap."""
    config = get_config()
    manager = ProductManager()

    with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"), console=console) as progress:
        if source == "csv" and file:
            progress.add_task("CSV dosyasi okunuyor...", total=None)
            products = import_products_from_csv(file)
            console.print(f"[green]{len(products)} urun CSV'den yuklendi[/green]")
        elif product_id:
            progress.add_task("Urun cekiliyor...", total=None)
            product = asyncio.run(manager.fetch_product(product_id))
            if not product:
                console.print(f"[red]Urun bulunamadi: {product_id}[/red]")
                raise typer.Exit(1)
            products = [product]
        else:
            progress.add_task("Urunler ikas'tan cekiliyor...", total=None)
            products = asyncio.run(manager.fetch_products())

    console.print(Panel(f"[bold]{len(products)} urun analiz ediliyor...[/bold]", title="SEO Analizi"))

    results = manager.analyze_products(products, threshold=threshold)

    table = Table(title="SEO Analiz Sonuclari")
    table.add_column("ID", style="dim", max_width=12)
    table.add_column("Urun Adi", max_width=40)
    table.add_column("Skor", justify="center")
    table.add_column("Baslik", justify="center")
    table.add_column("Aciklama", justify="center")
    table.add_column("Meta", justify="center")
    table.add_column("Sorunlar", max_width=40)

    for product, score in results:
        color = score_color(score.total_score)
        table.add_row(
            product.id[:12],
            product.name[:40],
            f"[{color}]{score.total_score}[/{color}]",
            str(score.title_score),
            str(score.description_score),
            str(score.meta_score),
            "; ".join(score.issues[:3]),
        )

    console.print(table)
    console.print(f"\n[bold]Toplam:[/bold] {len(results)} urun esik degerin ({threshold}) altinda")


@app.command()
def rewrite(
    dry_run: bool = typer.Option(False, help="Sadece goster, ikas'a yazma"),
    model: str = typer.Option("claude-haiku-4-5-20251001", help="Claude model"),
    threshold: int = typer.Option(70, help="Yeniden yazma esik degeri"),
) -> None:
    """Claude ile SEO icerikleri yeniden yaz."""
    manager = ProductManager()
    products = manager.get_cached_products()

    if not products:
        console.print("[yellow]Once 'analyze' komutunu calistirin[/yellow]")
        raise typer.Exit(1)

    results = manager.analyze_products(products, threshold=threshold)
    if not results:
        console.print("[green]Tum urunler esik degerin uzerinde![/green]")
        return

    console.print(Panel(f"[bold]{len(results)} urun icin Claude ile yeniden yaziliyor...[/bold]", title="SEO Rewrite"))

    with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"), console=console) as progress:
        task = progress.add_task("Rewrite islemi devam ediyor...", total=len(results))
        suggestions = manager.rewrite_products(results)
        progress.update(task, completed=len(results))

    for suggestion in suggestions:
        console.print(Panel(
            f"[bold]Urun:[/bold] {suggestion.original_name}\n"
            f"[bold]Onerilen Ad:[/bold] {suggestion.suggested_name or '-'}\n"
            f"[bold]Meta Title:[/bold] {suggestion.suggested_meta_title}\n"
            f"[bold]Meta Desc:[/bold] {suggestion.suggested_meta_description}\n"
            f"[bold]Aciklama:[/bold] {suggestion.suggested_description[:200]}...",
            title="Oneri",
            border_style="cyan",
        ))

    usage = manager.get_token_usage()
    console.print(f"\n[dim]Token kullanimi: {usage['input']} input, {usage['output']} output[/dim]")
    console.print(f"[dim]Tahmini maliyet: ${usage['estimated_cost']}[/dim]")

    if not dry_run and suggestions:
        _interactive_approve(manager, suggestions)


def _interactive_approve(manager: ProductManager, suggestions: list) -> None:
    console.print(f"\n[bold][{len(suggestions)} urun hazir][/bold]")
    choice = console.input("(a) Tumunu onayla  (r) Tek tek incele  (s) Atla  (q) Cikis: ")

    if choice == "a":
        for s in suggestions:
            manager.approve_suggestion(s.product_id)
        console.print("[green]Tum oneriler onaylandi[/green]")
    elif choice == "r":
        for s in suggestions:
            console.print(f"\n[bold]{s.original_name}[/bold] -> {s.suggested_name or '-'}")
            sub = console.input("(y) Onayla  (n) Reddet  (s) Atla: ")
            if sub == "y":
                manager.approve_suggestion(s.product_id)
                console.print("[green]Onaylandi[/green]")
            elif sub == "n":
                manager.reject_suggestion(s.product_id)
                console.print("[red]Reddedildi[/red]")
    elif choice == "q":
        raise typer.Exit()


@app.command()
def apply() -> None:
    """Onaylanmis degisiklikleri ikas'a uygula."""
    manager = ProductManager()
    approved = manager.get_approved_suggestions()

    if not approved:
        console.print("[yellow]Onaylanmis oneri yok. Once 'rewrite' komutunu calistirin.[/yellow]")
        return

    console.print(Panel(f"[bold]{len(approved)} oneri uygulanacak[/bold]", title="Uygulama"))

    config = get_config()
    if config.dry_run:
        console.print("[yellow]DRY RUN modu aktif - degisiklikler uygulanmayacak[/yellow]")

    applied = asyncio.run(manager.apply_suggestions(approved))
    console.print(f"[green]{applied} urun guncellendi[/green]")


@app.command()
def history() -> None:
    """Gecmis islemleri goster."""
    ops = db.get_operation_history(limit=20)

    if not ops:
        console.print("[dim]Henuz islem gecmisi yok[/dim]")
        return

    table = Table(title="Islem Gecmisi")
    table.add_column("Tarih", style="dim")
    table.add_column("Islem")
    table.add_column("Urun ID", max_width=12)
    table.add_column("Durum", justify="center")

    for op in ops:
        status = "[green]Basarili[/green]" if op["success"] else "[red]Basarisiz[/red]"
        table.add_row(
            str(op["created_at"]),
            op["operation"],
            str(op["product_id"])[:12],
            status,
        )

    console.print(table)


@app.command()
def test_connection() -> None:
    """API baglanti testi yap."""
    manager = ProductManager()

    with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"), console=console) as progress:
        progress.add_task("ikas API'ye baglaniliyor...", total=None)
        result = asyncio.run(manager.test_connection())

    if result:
        console.print("[green]ikas API baglantisi basarili![/green]")
    else:
        console.print("[red]ikas API baglantisi basarisiz. .env ayarlarinizi kontrol edin.[/red]")


@app.command()
def export(
    output: str = typer.Option("seo_report.csv", help="Cikti dosyasi"),
) -> None:
    """Onerileri CSV olarak disari aktar."""
    suggestions = db.get_pending_suggestions()
    if not suggestions:
        console.print("[yellow]Disa aktarilacak oneri yok[/yellow]")
        return

    path = export_suggestions_to_csv(suggestions, output)
    console.print(f"[green]{len(suggestions)} oneri disa aktarildi: {path}[/green]")
