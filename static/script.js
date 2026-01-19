type_dict={ 
     "koncerty": "koncert", 
     "artysci": "artystę", 
     "miejsca": "miejsce",
     "uzytkownicy": "użytkownika"
};

// Zamknięcie modala
function closeModal() {
    const modal = document.getElementById('modal');
    modal.style.display = 'none';
    const preview = document.getElementById('img-preview');
    if (preview) preview.style.display = 'none';
}

function closeView(e) {
    if (e.target.id === 'viewModal') {
        document.getElementById('viewModal').style.display = 'none';
    }
}

// Podgląd obrazka
const fileInput = document.getElementById('fileInput');
if (fileInput) {
    fileInput.addEventListener('change', function(e) {
        const preview = document.getElementById('img-preview');
        const file = e.target.files[0];
        
        if (file && preview) {
            preview.src = URL.createObjectURL(file);
            preview.style.display = 'block';
        }
    });
}

// Okno potwierdzenia
function customConfirm(message) {
    return new Promise((resolve) => {
        const modal = document.getElementById('confirmModal');
        const messageElement = document.getElementById('confirmMessage');
        const yesBtn = document.getElementById('confirmYes');
        messageElement.innerText = message;
        modal.style.display = 'flex';
        yesBtn.onclick = () => {
            modal.style.display = 'none';
            resolve(true);
        };
        window.closeConfirm = () => {
            modal.style.display = 'none';
            resolve(false); 
        };
    });
}

// Otwieranie modalu dodawania
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
        
        // koncerty
        if (type === 'koncerty') {
            form.id_artysty.value = data.id_artysty;
            form.id_miejsca.value = data.id_miejsca;
            form.opis.value = data.opis;
            form.data.value = data.data; 
            form.czas.value = data.czas;
            form.cena_biletu.value = data.cena_biletu;
        } 
        // artysci
        else if (type === 'artysci') {
            form.nazwa.value = data.nazwa;
            form.id_gatunku.value = data.id_gatunku;
        }
        // miejsca
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
        if (data.zdjecie) {
            previewImg.src = `/static/images/${type}/${data.zdjecie}`;
            previewImg.style.display = 'block';
        }

        document.querySelector('.modal-content h2').innerText = `Edytuj ${type_dict[type]}`;
        document.getElementById('modal').style.display = 'flex';
    } catch (error) {
        console.error('Błąd:', error);
        alert('Nie udało się załadować danych do edycji.');
    }
}

// Submit
const addForm = document.getElementById('addForm');
if (addForm) {
    addForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        const form = e.target;
        const type = form.dataset.type;
        const id = document.getElementById('id').value;
        const formData = new FormData(form);
    
        const url = id ? `/${type}/edytuj` : `/${type}/dodaj`;
        try {
            const response = await fetch(url, { method: 'POST', body: formData });
            if (response.ok) {
                location.reload();
            } else {
                const errorData = await response.json();
                alert("Błąd: " + (errorData.message || "Nie udało się zapisać danych"));
            }
        } catch (error) {
            console.error("Błąd połączenia:", error);
        }
    });
}

// Usuwanie
async function deleteItem(type, id) {
    const confirmed = await customConfirm(`Czy na pewno chcesz usunąć ${type_dict[type]}?`);
    if (confirmed) {
        try {
            const response = await fetch(`/${type}/usun/${id}`, { method: 'DELETE' });
            if (response.ok) {
                location.reload();
            } else {
                alert('Błąd podczas usuwania.');
            }
        } catch (error) {
            console.error('Błąd:', error);
        }
    }
}

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
    } catch (error) {
        console.error('Błąd podglądu:', error);
    }
}

function buyTicket(id) {
    window.location.href = `/zamowienie/${id}`;
}

function showReport(sectionId) {
    const contents = document.querySelectorAll('.report-content');
    contents.forEach(content => content.style.display = 'none');
    const buttons = document.querySelectorAll('.tab-btn');
    buttons.forEach(btn => btn.classList.remove('active'));

    document.getElementById(sectionId).style.display = 'block';
    event.currentTarget.classList.add('active');
}

function updateTotal() {
    const qty = document.getElementById('ticketQuantity').value;
    const price = document.getElementById('unitPrice').innerText;
    document.getElementById('totalPrice').innerText = (qty * price).toFixed(2);
}

async function confirmPurchase() {
    const form = document.getElementById('purchaseForm');
    const formconcert = new FormData(form);

    const response = await fetch('/kup-bilet', { method: 'POST', body: formconcert });
    const result = await response.json();

    if (result.status === 'success') {
        window.location.href = '/bilety'; 
    } else {
        alert('Błąd: ' + result.message);
    }
}