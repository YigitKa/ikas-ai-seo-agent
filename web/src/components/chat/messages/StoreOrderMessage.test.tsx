import { render, screen } from '@testing-library/react';
import AssistantMessageContent from './AssistantContent';
import { parseStoreOrderMessage } from './storeOrderMessageParser';

describe('parseStoreOrderMessage', () => {
  it('parses guided recent order markdown into structured data', () => {
    const parsed = parseStoreOrderMessage(`**Son Siparisler**
- Gosterilen siparis: 2
- #2760 | 09.04.2026 10:28 | durum: CREATED | odeme: PAID | toplam: 26046.39 | musteri: - | urunler: Canna Terra Professional 50 Litre x4, Voodoo Juice 500 mL x2, +6 urun daha

**Not**
- Bu liste ikas MCP canli verisinden dogrudan alindi.`);

    expect(parsed).not.toBeNull();
    expect(parsed?.kind).toBe('recent_orders');
    expect(parsed?.orders[0]).toMatchObject({
      orderNumber: '2760',
      status: 'CREATED',
      paymentStatus: 'PAID',
      extraItemsText: '+6 urun daha',
    });
  });
});

describe('StoreOrderMessage rendering', () => {
  it('renders recent orders as a designed card instead of raw list rows', () => {
    render(
      <AssistantMessageContent
        content={`**Son Siparisler**
- Gosterilen siparis: 2
- #2760 | 09.04.2026 10:28 | durum: CREATED | odeme: PAID | toplam: 26046.39 | musteri: - | urunler: Canna Terra Professional 50 Litre x4, Voodoo Juice 500 mL x2, +6 urun daha
- #2770 | 08.04.2026 16:15 | durum: CREATED | odeme: PAID | toplam: 300.56 | musteri: - | urunler: Growth Technology Cactus Focus x1

**Not**
- Bu liste ikas MCP canli verisinden dogrudan alindi.`}
      />,
    );

    expect(screen.getByText('Siparis Akisi')).toBeInTheDocument();
    expect(screen.getByText('Son Siparisler')).toBeInTheDocument();
    expect(screen.getByText('26.046,39')).toBeInTheDocument();
    expect(screen.getAllByText('Odendi').length).toBeGreaterThan(0);
    expect(screen.getByText('Canna Terra Professional 50 Litre x4')).toBeInTheDocument();
    expect(screen.queryByText(/#2760 \| 09\.04\.2026 10:28 \| durum:/i)).not.toBeInTheDocument();
  });
});
