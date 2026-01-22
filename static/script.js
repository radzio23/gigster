const type_dict = { 
    "koncerty": "koncert", 
    "artysci": "artystę", 
    "miejsca": "miejsce",
    "uzytkownicy": "użytkownika"
};

// ZAMYKANIE MODALI
function closeModal() {
    document.getElementById('modal').style.display = 'none';
    const preview = document.getElementById('img-preview');
    if (preview) preview.style.display = 'none';
}

function closeView(e) {
    if (e.target.id === 'viewModal') {
        document.getElementById('viewModal').style.display = 'none';
    }
}

// PODGLĄD ZDJĘCIA
const fileInput = document.getElementById('fileInput');
if (fileInput) {
    fileInput.addEventListener('change', function(e) {
        const preview = document.getElementById('img-preview');
        const file = e.target.files[0];
        
        if (file && preview) {
            if (preview.src.startsWith('blob:')) URL.revokeObjectURL(preview.src);
            preview.src = URL.createObjectURL(file);
            preview.style.display = 'block';
        }
    });
}

// MODAL POTWIERDZENIA
function customConfirm(message) {
    return new Promise((resolve) => {
        const modal = document.getElementById('confirmModal');
        document.getElementById('confirmMessage').innerText = message;
        modal.style.display = 'flex';

        document.getElementById('confirmYes').onclick = () => {
            modal.style.display = 'none';
            resolve(true);
        };
        window.closeConfirm = () => {
            modal.style.display = 'none';
            resolve(false); 
        };
    });
}


// MODUŁ CRUD: OTWIERANIE MODALI DODAWANIA I EDYCJI
function openAddModal(type) {
    const form = document.getElementById('addForm');
    form.reset();
    document.getElementById('id').value = '';
    document.getElementById('img-preview').style.display = 'none';
    
    form.dataset.type = type; 
    document.querySelector('.modal-content h2').innerText = `Nowy ${type_dict[type]}`;
    document.getElementById('modal').style.display = 'flex';
}

async function openEditModal(type, id) {    
    try {
        const response = await fetch(`/${type}/${id}`);
        if (!response.ok) throw new Error('Błąd pobierania danych');
        
        const data = await response.json();
        const form = document.getElementById('addForm');
        form.dataset.type = type;
        document.getElementById('id').value = data.id;
        let isoDate;
        if (data.data) {
            const [day, month, year] = data.data.split('.');
            isoDate = `${year}-${month}-${day}`;
        }
        
        if (type === 'koncerty') {
            form.id_artysty.value = data.id_artysty;
            form.id_miejsca.value = data.id_miejsca;
            form.opis.value = data.opis;
            form.data.value = isoDate;
            form.czas.value = data.czas;
            form.cena_biletu.value = data.cena_biletu;
        } 
        else if (type === 'artysci') {
            form.nazwa.value = data.nazwa;
            form.id_gatunku.value = data.id_gatunku;
        }
        else if (type === 'miejsca') {
            form.nazwa.value = data.nazwa;
            form.miasto.value = data.miasto;
            form.adres.value = data.adres;
            form.pojemnosc.value = data.pojemnosc;
        }
        else if (type === 'uzytkownicy') {
            form.nazwa.value = data.nazwa;
            form.rola.value = data.rola;
            if (form.haslo) form.haslo.value = ''; 
        }

        const previewImg = document.getElementById('img-preview');
        if (data.zdjecie && previewImg) {
            previewImg.src = `/static/images/${type}/${data.zdjecie}`;
            previewImg.style.display = 'block';
        }

        document.querySelector('.modal-content h2').innerText = `Edytuj ${type_dict[type]}`;
        document.getElementById('modal').style.display = 'flex';
    } catch (error) {
        console.error('Błąd:', error);
        alert('Nie udało się załadować danych.');
    }
}

// ZAPIS DANYCH (DODAWANIE I EDYCJA)
const addForm = document.getElementById('addForm');
if (addForm) {
    addForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        const type = e.target.dataset.type;
        const id = document.getElementById('id').value;
        const formData = new FormData(e.target);
    
        const url = id ? `/${type}/edytuj` : `/${type}/dodaj`;
        try {
            const response = await fetch(url, { method: 'POST', body: formData });
            if (response.ok) location.reload();
            else {
                const err = await response.json();
                alert("Błąd: " + (err.message || "Błąd zapisu"));
            }
        } catch (error) { console.error("Błąd połączenia:", error); }
    });
}

async function deleteItem(type, id) {
    if (await customConfirm(`Czy na pewno chcesz usunąć ${type_dict[type]}?`)) {
        try {
            const response = await fetch(`/${type}/usun/${id}`, { method: 'DELETE' });
            if (response.ok) location.reload();
            else alert('Błąd podczas usuwania.');
        } catch (error) { console.error('Błąd:', error); }
    }
}

// MODAL PODGLĄDU KONCERTU
async function openViewModal(id) {
    try {
        const response = await fetch(`/koncerty/${id}`);
        const data = await response.json();
        const role = document.body.dataset.role;

        let details = `
            <div class="view-info">
                <h1>${data.opis}</h1>
                <h2>${data.artysta_nazwa}</h2>
                <hr>
                <div>
                    <div class="info-block">
                        <div><span>◴</span> ${data.data}, ${data.czas}</div>
                        <div><span>⚲</span> ${data.miejsce_nazwa}</div>
                        <div><span>🛈</span> ${data.miasto}, ${data.adres}</div>
                    </div>
        `;
        if(role == 'user') {
            const dostepneMiejsca = data.pojemnosc - data.sprzedane;
            if (dostepneMiejsca <= 0) {
                details += `
                    <div class="sold-out">
                        <p class="center" style="color: #ff4d4d; font-weight: bold; font-size: 1.2rem;">WYPRZEDANE</p>
                    </div>
                `;
            } else {
                details += `
                    <div>
                        <p class="center">Bilety od ${data.cena_biletu} zł</p>
                        <button class="buy-ticket-btn" onclick="buyTicket(${data.id})">KUP BILET</button>
                        <p class="center">Dostępne bilety: ${dostepneMiejsca} / ${data.pojemnosc}</p>
                    </div>
                `;
            }
        }
        else if(role == 'admin') details += `
            <p class="center">Zaloguj się jako użytkownik, aby kupić bilet.</p>
            `;
        else details += `
            <p class="center">Zaloguj się, aby kupić bilet.</p>
            `;
            
        details += `
                </div>
            </div>
            <div class="img-container">
                <div class="blur-bg" style="background-image: url('/static/images/koncerty/${data.zdjecie}');"></div>
                <img src="/static/images/koncerty/${data.zdjecie}" alt="Zdjęcie koncertu">
            </div>
            `;

        document.getElementById('viewDetails').innerHTML = details;
        document.getElementById('viewModal').style.display = 'flex';
    } catch (error) { console.error('Błąd podglądu:', error); }
}

// MODUŁ ZAKUPU BILETU
function buyTicket(id) {
    window.location.href = `/zamowienie/${id}`;
}

function showReport(sectionId) {
    document.querySelectorAll('.report-content').forEach(c => c.style.display = 'none');
    document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
    document.getElementById(sectionId).style.display = 'block';
    event.currentTarget.classList.add('active');
}

function updateTotal() {
    const qty = document.getElementById('ticketQuantity').value;
    const price = parseFloat(document.getElementById('unitPrice').innerText);
    document.getElementById('totalPrice').innerText = (qty * price).toFixed(2);
}

async function confirmPurchase() {
    const formData = new FormData(document.getElementById('purchaseForm'));
    const response = await fetch('/kup-bilet', { method: 'POST', body: formData });
    const result = await response.json();

    if (result.status === 'success') window.location.href = '/bilety'; 
    else alert('Błąd: ' + result.message);
}