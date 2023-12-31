from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import re, time, json, os
import pandas as pd
from datetime import date
from collections import defaultdict

# Une fonction pour s'authentifier : comment gérer les secrets ?


def authentication(driver, url_authentication, config):

    driver.get(url_authentication)

    id_login = WebDriverWait(driver, 10).until(
        EC.presence_of_element_located(
            (By.ID, "id_login")
        ))

    id_login.send_keys(config['username'])
    driver.find_element(By.ID, "id_password").send_keys(config['password'])

    driver.find_element(By.ID, "id_remember").click()
    driver.find_element(By.CLASS_NAME, "custom-login-button").click()

    return


def lit_les_ressource(driver, url_ressources):
    driver.get(url_ressources)

    compteur_ressources = WebDriverWait(driver, 10).until(
        EC.presence_of_element_located(
            (By.XPATH, "//h1/span")
        ))

    nombre_ressources = re.findall('[0-9]+', compteur_ressources.text)[0]

    assert int(nombre_ressources) == len(driver.find_elements(By.CLASS_NAME, "col-xxl-3"))   # On  s'assure que toutes les col-xxl-3 sont des ressources

    ressources = {}

    for ix in range(len(driver.find_elements(By.CLASS_NAME, "col-xxl-3"))):
        time.sleep(1)
        element = WebDriverWait(driver, 10).until(
            EC.presence_of_all_elements_located(
                (By.CLASS_NAME, "col-xxl-3")
            ))[ix]
        # element = driver.find_elements(By.CLASS_NAME, "col-xxl-3")[ix]
        element_name = element.find_element(By.TAG_NAME, 'a').text
        element_url = element.find_element(By.TAG_NAME, 'a').get_attribute('href')
        driver.get(element_url)
        element_modifie = driver.find_element(By.XPATH, "//div[@id='resource-details']/div/span/em").text
        # print(driver.find_element(By.XPATH, '//div[@id = "resource-main"]/div[@class = "text-justified font-marianne"]').text)
        sous_page = driver.find_element(By.XPATH, '//div[@id = "resource-main"]/div[@class = "text-justified font-marianne"]').get_attribute('innerHTML')
        taches_liees = [tache.get_attribute('href') for tache in driver.find_elements(By.XPATH, "//ul[@class='mt-3 text-grey-light']/li/a")]

        assert element_name not in ressources.keys()  # Pas de doublons dans les noms

        ressources[element_name] = {
            "date_modification": element_modifie,
            "contenu": sous_page,
            "url": element_url,
            "taches_liees": taches_liees
            }

        driver.get(url_ressources)

        time.sleep(1)

    return ressources


def lit_la_liste_des_taches(driver):

    driver.find_element(By.PARTIAL_LINK_TEXT, "Export CSV").click()   # TODO lire en mémoire directement

    file_path = f'urbanvitaliz-projects-{date.today().strftime("%Y-%m-%d")}.csv'
    export = pd.read_csv(file_path, usecols = ['statut_conseil', 'lien_projet', 'departement'])

    os.remove(file_path)

    return export


def lit_une_tache(driver, url_tache, lire_recommandations):

    driver.get(url_tache)
    time.sleep(1)

    xpath_contexte = "//h6[contains(text(), 'Contexte')]/ancestor::div/following-sibling::div/article"
    contexte = WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.XPATH, xpath_contexte))).text

    xpath_complements = "//h6[contains(text(), 'Compléments')]/ancestor::div/following-sibling::div/article"
    complements = driver.find_element(By.XPATH, xpath_complements).text

    tache = {'id': url_tache, 'contexte': contexte, 'complements': complements}

    if lire_recommandations:
        onglet_recommandations = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located(
                (By.ID, "overview-step-2")))

        onglet_recommandations.click()
        time.sleep(1)
        recommandations = [recommandation.text for recommandation in driver.find_elements(By.XPATH, "//h6")]
        tache['recommandations'] = recommandations

    return tache


# Une fonction pour aller siphonner les tâches à traiter / en attente / en cours (test set en lien avec le métier) vs
# traitées (train & validation)


def lit_les_taches(driver, url_taches):

    driver.get(url_taches)

    # La liste des url des tâches par état est disponible dans un csv dans le site.
    # L'acquérir semble plus robuste que scraper les tâches une à une à cause du slider

    taches = defaultdict(dict)

    liste_des_taches = lit_la_liste_des_taches(driver)

    for ix, tache in liste_des_taches.iterrows():
        tache_extraite = lit_une_tache(driver, tache['lien_projet'], tache['statut_conseil'] == "DONE")
        tache_extraite['departement'] = tache['departement']
        taches[tache['statut_conseil']][tache_extraite['id']] = tache_extraite

    return taches

# Consolider les recommandations présentes dans les taches avec les fiches


def consolider_recommandations(ressources, taches):

    taches_ressources_url = taches.copy()
    taches_ressources_url['DONE'] = dict()  # On réécrit les tâches effectuées pour inclure les url des ressources

    # Méthode 1 : ressources présentes dans l'onglet "recommandations" de chaque tâche

    for entry_url, entry in taches['DONE'].items():
        entry['ressources_url_match_nom'] = list()
        entry['ressources_url_match_url'] = list()

        for ressource in entry["recommandations"]:
            if ressource in ressources.keys():
                entry['ressources_url_match_nom'].append(ressources[ressource]['url'])

        for ressource_url, ressource in ressources.items():
            if entry_url in ressource['taches_liees']:
                entry['ressources_url_match_url'].append(ressource['url'])

        taches_ressources_url['DONE'][entry_url] = entry

    with open('../ressources.json', 'w') as f:
        f.write(json.dumps(ressources))

    with open('../taches.json', 'w') as f:
        f.write(json.dumps(taches_ressources_url))

    return taches_ressources_url


# Sauvegarder le tout

if __name__ == '__main__':
    url_base = 'https://sosponts.recoconseil.fr'
    url_authentication = f'{url_base}/accounts/login/'
    url_ressources = f'{url_base}/ressource/'
    url_taches = f'{url_base}/projects/staff/'

    config_path = os.path.expanduser(os.path.join('~', '.config', 'sos-ponts', 'config.json'))

    with open(config_path, 'r') as f:
        config = json.loads(f.read())

    webdriver_service = Service(config['driver_path'])

    options = webdriver.FirefoxOptions()
    # options.headless = True
    options.set_preference("browser.download.folderList", 2)
    options.set_preference("browser.download.manager.showWhenStarting", False)
    options.set_preference("browser.download.dir", os.getcwd())
    options.set_preference("browser.helperApps.neverAsk.saveToDisk", "text/csv")

    driver = webdriver.Firefox(service=webdriver_service, options=options)

    sos_ponts = driver.get(url_base)

    no_cookies = WebDriverWait(driver, 10).until(
        EC.presence_of_element_located(
            (By.XPATH, "//button[@title='Refuser tous les cookies']")
            )
        )

    no_cookies.click()

    authentication(driver, url_authentication, config)
    ressources = lit_les_ressource(driver, url_ressources)
    taches = lit_les_taches(driver, url_taches)
    ressources_taches = consolider_recommandations(ressources, taches)
    print('haha')
